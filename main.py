import os
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

# Bibliotecas externas usadas para carregar as configuracoes, criar o servidor
# web e acessar a API de inteligencia artificial do Gemini.
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pydantic import BaseModel, Field, PrivateAttr

from contador_token import ResumoCusto, calcular_custo


# Modelo de IA usado em todas as consultas feitas pela aplicacao.
MODELO = "gemini-2.5-flash"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

# Instrucoes permanentes que definem o papel do Gemini e o formato esperado
# para as recomendacoes de jogos.
PROMPT_SISTEMA = """
Você é um assistente especializado em jogos para PlayStation 5.

Ajude o usuário a escolher jogos com base em suas preferências.

Regras:
- Recomende no máximo 3 jogos.
- Informe nome, gênero e uma breve descrição.
- Diga se possui campanha, multiplayer ou cooperativo.
- Informe o perfil de jogador recomendado.
- Informe a nota da critica na escala de 0 a 100 e a nota dos jogadores de 0 a 10.
- Use o consenso de avaliacoes conhecido; se nao tiver confianca, retorne nulo para a nota.
- Classifique a dificuldade no modo padrao, sem considerar opcoes de acessibilidade.
- Recomende apenas jogos disponíveis para PlayStation 5; não precisa ser exclusivo.
- Caso faltem informações, pergunte sobre gênero, orçamento e preferência por campanha ou multiplayer.
- Responda de forma clara, objetiva e amigável.
- Informe o menor valor ja registrado para o game e um preço justo.
- Preencha todos os campos do JSON de acordo com o schema fornecido.
- Não use Markdown nem acrescente texto fora da estrutura JSON.
- Caso faltem informações, retorne a lista de jogos vazia e use o campo pergunta_complementar.
"""


# Define e valida o formato de cada jogo devolvido pelo Gemini.
class JogoRecomendado(BaseModel):
    _imagem_url: str | None = PrivateAttr(default=None)

    nome: str = Field(description="Nome comercial do jogo.")
    genero: str = Field(description="Genero principal do jogo.")
    descricao: str = Field(description="Resumo curto, claro e sem Markdown.")
    modos: list[Literal["Campanha", "Multiplayer", "Cooperativo"]] = Field(
        description="Modos de jogo disponiveis.",
        min_length=1,
    )
    perfil_jogador: str = Field(description="Perfil de jogador recomendado.")
    menor_preco_historico: str = Field(
        description="Menor preco historico em reais ou 'Nao informado'."
    )
    preco_justo: str = Field(
        description="Faixa de preco considerada justa em reais."
    )
    nota_jogadores: float | None = Field(
        default=None,
        description="Nota media dos jogadores de 0 a 10 ou nulo se desconhecida.",
        ge=0,
        le=10,
    )
    nota_critica: int | None = Field(
        default=None,
        description="Nota media da critica de 0 a 100 ou nulo se desconhecida.",
        ge=0,
        le=100,
    )
    dificuldade: Literal[
        "Muito fácil",
        "Fácil",
        "Moderada",
        "Difícil",
        "Muito difícil",
    ] = Field(description="Dificuldade geral do jogo no modo padrao.")
    @property
    def imagem_url(self) -> str | None:
        """Retorna a capa localizada pelo servidor fora do schema do Gemini."""
        return self._imagem_url


# Estrutura completa que o Flask espera receber da API.
class RespostaRecomendacao(BaseModel):
    introducao: str = Field(description="Mensagem breve que contextualiza a resposta.")
    jogos: list[JogoRecomendado] = Field(
        description="Ate tres jogos recomendados; lista vazia se faltarem dados.",
        max_length=3,
    )
    pergunta_complementar: str | None = Field(
        default=None,
        description="Pergunta ao usuario quando faltarem preferencias importantes.",
    )

# Cria a aplicacao Flask. O nome do modulo permite que o Flask localize as
# pastas "templates" e "static" automaticamente.
app = Flask(__name__)


def criar_cliente() -> genai.Client:
    """Carrega a chave da API e cria o cliente do Gemini."""
    # Le as variaveis definidas no arquivo .env do projeto.
    load_dotenv()
    chave_api = os.getenv("GEMINI_API_KEY")

    # Interrompe a operacao com uma mensagem clara quando a chave nao existe.
    if not chave_api:
        raise ValueError(
            "A variável GEMINI_API_KEY não foi encontrada no arquivo .env."
        )

    return genai.Client(api_key=chave_api)


def gerar_resposta(
    cliente: genai.Client,
    pergunta: str,
    prompt_sistema: str = PROMPT_SISTEMA,
) -> tuple[RespostaRecomendacao, ResumoCusto]:
    """Devolve a resposta validada e o custo calculado pelos metadados."""
    # Envia a pergunta, as regras do sistema e a configuracao de criatividade.
    resposta = cliente.models.generate_content(
        model=MODELO,
        contents=pergunta,
        config=types.GenerateContentConfig(
            system_instruction=prompt_sistema,
            temperature=0.4,
            response_mime_type="application/json",
            response_schema=RespostaRecomendacao,
        ),
    )

    # O SDK converte o JSON para o modelo Pydantic definido acima.
    if not isinstance(resposta.parsed, RespostaRecomendacao):
        raise RuntimeError("O Gemini não retornou o JSON no formato esperado.")

    custo = calcular_custo(resposta.usage_metadata, MODELO)
    return resposta.parsed, custo


def normalizar_titulo(texto: str) -> str:
    """Remove acentos e sinais para comparar nomes de jogos."""
    sem_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(
        caractere.casefold()
        for caractere in sem_acentos
        if caractere.isalnum()
    )


def extrair_melhor_imagem(dados: dict, nome_jogo: str) -> str | None:
    """Escolhe a imagem da pagina com titulo mais proximo ao nome do jogo."""
    paginas = dados.get("query", {}).get("pages", {}).values()
    titulo_normalizado = normalizar_titulo(nome_jogo)
    candidatos: list[tuple[float, str]] = []

    for pagina in paginas:
        origem = pagina.get("thumbnail", {}).get("source")
        if not origem:
            continue

        endereco = urlparse(origem)
        if endereco.scheme != "https" or endereco.hostname != "upload.wikimedia.org":
            continue

        similaridade = SequenceMatcher(
            None,
            titulo_normalizado,
            normalizar_titulo(str(pagina.get("title", ""))),
        ).ratio()
        candidatos.append((similaridade, origem))

    if not candidatos:
        return None

    similaridade, origem = max(candidatos, key=lambda candidato: candidato[0])
    return origem if similaridade >= 0.6 else None


@lru_cache(maxsize=128)
def buscar_imagem_wikipedia(nome_jogo: str) -> str | None:
    """Busca a capa do jogo na Wikipedia e guarda o resultado em cache."""
    parametros_base = {
        "action": "query",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": 700,
        "pilicense": "any",
        "format": "json",
    }
    cabecalhos = {"User-Agent": "NextPlay/1.0 (game recommendation project)"}

    try:
        # A primeira tentativa resolve nomes exatos e redirecionamentos, como
        # "God of War Ragnarok" para "God of War Ragnarök".
        resposta = requests.get(
            WIKIPEDIA_API_URL,
            params={**parametros_base, "titles": nome_jogo, "redirects": 1},
            headers=cabecalhos,
            timeout=8,
        )
        resposta.raise_for_status()
        imagem = extrair_melhor_imagem(resposta.json(), nome_jogo)
        if imagem:
            return imagem

        # Se o titulo nao for exato, pesquisa artigos relacionados e escolhe
        # aquele cujo nome mais se aproxima do jogo recomendado.
        resposta = requests.get(
            WIKIPEDIA_API_URL,
            params={
                **parametros_base,
                "generator": "search",
                "gsrsearch": f'"{nome_jogo}" video game',
                "gsrlimit": 5,
            },
            headers=cabecalhos,
            timeout=8,
        )
        resposta.raise_for_status()
        return extrair_melhor_imagem(resposta.json(), nome_jogo)
    except (requests.RequestException, ValueError):
        return None


def adicionar_imagens(jogos: list[JogoRecomendado]) -> None:
    """Busca ate tres capas em paralelo e as associa aos jogos."""
    if not jogos:
        return

    with ThreadPoolExecutor(max_workers=len(jogos)) as executor:
        imagens = executor.map(
            buscar_imagem_wikipedia,
            [jogo.nome for jogo in jogos],
        )

    for jogo, imagem in zip(jogos, imagens):
        jogo._imagem_url = imagem


def obter_tempo_espera(erro: ClientError) -> int | None:
    """Extrai do erro do Gemini o tempo sugerido para uma nova tentativa."""
    detalhes = erro.details.get("error", {}).get("details", [])
    for detalhe in detalhes:
        if not str(detalhe.get("@type", "")).endswith("RetryInfo"):
            continue

        valor = str(detalhe.get("retryDelay", "")).removesuffix("s")
        try:
            return max(1, int(float(valor)) + 1)
        except ValueError:
            return None

    return None


# Rota que renderiza a pagina principal quando o navegador acessa o site.
@app.get("/")
def pagina_inicial():
    return render_template("index.html")


# Endpoint chamado pelo JavaScript para gerar uma nova recomendacao.
@app.post("/api/recomendar")
def recomendar():
    # Le o JSON sem gerar excecao caso o corpo esteja vazio ou seja invalido.
    dados = request.get_json(silent=True) or {}
    pergunta = str(dados.get("pergunta", "")).strip()

    # Valida a pergunta antes de consumir a API externa.
    if not pergunta:
        return jsonify({"erro": "Conte um pouco sobre o jogo que você procura."}), 400

    if len(pergunta) > 1500:
        return jsonify({"erro": "A pergunta deve ter no máximo 1.500 caracteres."}), 400

    try:
        # O Gemini devolve dados estruturados e o Flask monta o fragmento HTML.
        cliente = criar_cliente()
        recomendacao, custo = gerar_resposta(cliente, pergunta)

        # A capa e complementar e nunca deve invalidar a resposta do Gemini.
        try:
            adicionar_imagens(recomendacao.jogos)
        except Exception:
            app.logger.exception("Falha ao buscar capas dos jogos")

        html = render_template(
            "_recomendacao.html",
            recomendacao=recomendacao,
        )
        return jsonify(
            {
                "recomendacao": recomendacao.model_dump(mode="json"),
                "html": html,
                "uso": custo.para_dict(),
            }
        )
    except ClientError as erro:
        if erro.code == 429:
            espera = obter_tempo_espera(erro)
            mensagem = "O limite de uso do Gemini foi atingido."
            if espera:
                mensagem += f" Tente novamente em aproximadamente {espera} segundos."
            else:
                mensagem += " Aguarde alguns instantes e tente novamente."

            resposta = jsonify({"erro": mensagem, "codigo": "quota_excedida"})
            if espera:
                resposta.headers["Retry-After"] = str(espera)
            return resposta, 429

        if erro.code in (401, 403):
            return jsonify(
                {
                    "erro": "A chave do Gemini e invalida ou nao possui permissao.",
                    "codigo": "chave_invalida",
                }
            ), 502

        app.logger.exception("O Gemini rejeitou a solicitacao")
        return jsonify(
            {
                "erro": f"O Gemini rejeitou a solicitacao (erro {erro.code}).",
                "codigo": "erro_gemini",
            }
        ), 502
    except ValueError as erro:
        # Informa erros de configuracao, como a ausencia da chave da API.
        return jsonify({"erro": str(erro)}), 500
    except Exception:
        # Registra o erro tecnico e envia uma mensagem segura ao navegador.
        app.logger.exception("Falha ao acessar a API do Gemini")
        return jsonify(
            {"erro": "Não foi possível consultar o Gemini agora. Tente novamente."}
        ), 502


# Funcao auxiliar para testar uma pergunta diretamente pelo terminal. O site
# normalmente utiliza a rota /api/recomendar.
def main() -> None:
    try:
        print("Resposta gerada pelo Gemini:\n")
        print(gerar_resposta(criar_cliente(), PERGUNTA))
    except (ValueError, RuntimeError) as erro:
        print(f"Erro: {erro}")
    except Exception as erro:
        print(f"Erro inesperado ao acessar a API do Gemini: {erro}")


# Inicia o servidor apenas quando este arquivo e executado diretamente.
if __name__ == "__main__":
    app.run(debug=True)
