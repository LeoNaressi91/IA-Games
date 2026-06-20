# NextPlay

Aplicação web que usa a API do Google Gemini para recomendar jogos disponíveis no PlayStation 5 com base nas preferências do usuário.

O NextPlay sugere até três jogos e apresenta gênero, descrição, modos de jogo, perfil recomendado, dificuldade, avaliações e estimativas de preço. A aplicação também busca capas na Wikipédia e exibe o consumo de tokens e o custo estimado de cada consulta.

## Funcionalidades

- Recomendações personalizadas de jogos para PS5.
- Respostas estruturadas e validadas com Pydantic.
- Até três sugestões por consulta.
- Informações sobre campanha, multiplayer e modo cooperativo.
- Notas de jogadores e da crítica.
- Menor preço histórico e faixa de preço considerada justa.
- Capas obtidas por meio da API da Wikipédia.
- Contagem de tokens e estimativa de custo da chamada ao Gemini.
- Tratamento de erros de configuração, autenticação e limite de uso da API.

## Tecnologias

- Python 3.12
- Flask
- Google Gen AI SDK
- Pydantic
- python-dotenv
- Requests
- HTML, CSS e JavaScript

## Pré-requisitos

- Python 3.12 ou uma versão compatível instalada.
- Uma chave de API do Google Gemini.

## Instalação

No PowerShell, entre na pasta do projeto e crie um ambiente virtual:

```powershell
cd curso_gemini
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

No Linux ou macOS, a ativação do ambiente virtual é feita com:

```bash
source .venv/bin/activate
```

## Configuração

Crie um arquivo `.env` na raiz do projeto com a sua chave do Gemini:

```env
GEMINI_API_KEY=sua_chave_aqui
```

O arquivo `.env` está listado no `.gitignore` e não deve ser enviado ao repositório.

## Execução

Com o ambiente virtual ativado, inicie o servidor:

```powershell
python main.py
```

Depois, acesse no navegador:

```text
http://127.0.0.1:5000
```

Descreva o tipo de jogo desejado, incluindo detalhes como gênero, orçamento e preferência por campanha ou multiplayer. A aplicação enviará a solicitação ao modelo `gemini-2.5-flash` e exibirá as recomendações na página.

## Deploy no Render

O projeto inclui um Blueprint em `render.yaml`. Para publicar:

1. Envie o projeto para um repositório no GitHub, GitLab ou Bitbucket.
2. No Render, escolha **New > Blueprint** e conecte o repositório.
3. Informe o valor secreto de `GEMINI_API_KEY` quando solicitado.
4. Confirme a criação do serviço `nextplay`.

O Render instalará as dependências e iniciará a aplicação com Gunicorn. O arquivo `.env` local não é enviado ao repositório; em produção, a chave deve ser configurada somente como variável de ambiente do serviço.

## Estrutura do projeto

```text
curso_gemini/
|-- main.py
|-- contador_token.py
|-- requirements.txt
|-- static/
|   |-- app.js
|   `-- style.css
|-- templates/
|   |-- _recomendacao.html
|   `-- index.html
`-- README.md
```

- `main.py`: configura o Flask, consulta o Gemini, valida as respostas e busca as capas dos jogos.
- `contador_token.py`: calcula o consumo de tokens e o custo estimado da consulta.
- `templates/`: contém a página principal e o fragmento HTML das recomendações.
- `static/`: contém os estilos e a lógica JavaScript da interface.

## API

A interface utiliza o endpoint `POST /api/recomendar`.

Exemplo de requisição:

```json
{
  "pergunta": "Quero um RPG de mundo aberto com uma boa história para jogar sozinho."
}
```

Em caso de sucesso, a resposta inclui os dados estruturados da recomendação, o HTML renderizado e um resumo do uso de tokens. O campo de entrada aceita no máximo 1.500 caracteres.

## Observações

- As recomendações, avaliações e estimativas de preço são geradas por inteligência artificial e podem conter imprecisões.
- A busca de capas é complementar; uma falha na Wikipédia não impede a exibição das recomendações.
- A estimativa de custo usa as tarifas cadastradas em `contador_token.py` e pode ficar desatualizada caso o provedor altere seus preços.
