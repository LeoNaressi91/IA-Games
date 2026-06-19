"""Calcula tokens utilizados e custo estimado das respostas do Gemini."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any


# Tarifas Standard Paid Tier consultadas em 18/06/2026:
# https://ai.google.dev/gemini-api/docs/pricing
PRECOS_USD_POR_MILHAO = {
    "gemini-2.5-flash": {
        "entrada": Decimal("0.30"),
        "saida": Decimal("2.50"),
    }
}
UM_MILHAO = Decimal("1000000")


@dataclass(frozen=True)
class ResumoCusto:
    """Representa o consumo de tokens e a estimativa na tarifa paga."""

    modelo: str
    tokens_entrada: int
    tokens_resposta: int
    tokens_pensamento: int
    tokens_total: int
    custo_entrada_usd: float
    custo_saida_usd: float
    custo_total_usd: float
    disponivel: bool

    def para_dict(self) -> dict:
        """Converte o resumo para um objeto serializavel pelo Flask."""
        return asdict(self)


def calcular_custo(usage_metadata: Any, modelo: str) -> ResumoCusto:
    """Calcula o custo sem realizar uma nova chamada ao Gemini."""
    if modelo not in PRECOS_USD_POR_MILHAO:
        raise ValueError(f"Nao ha precos cadastrados para o modelo {modelo}.")

    precos = PRECOS_USD_POR_MILHAO[modelo]
    tokens_prompt = int(getattr(usage_metadata, "prompt_token_count", 0) or 0)
    tokens_ferramentas = int(
        getattr(usage_metadata, "tool_use_prompt_token_count", 0) or 0
    )
    tokens_resposta = int(
        getattr(usage_metadata, "candidates_token_count", 0) or 0
    )
    tokens_pensamento = int(
        getattr(usage_metadata, "thoughts_token_count", 0) or 0
    )
    tokens_entrada = tokens_prompt + tokens_ferramentas
    tokens_saida = tokens_resposta + tokens_pensamento
    tokens_total_calculado = tokens_entrada + tokens_saida
    tokens_total = int(
        getattr(usage_metadata, "total_token_count", 0) or tokens_total_calculado
    )

    custo_entrada = Decimal(tokens_entrada) * precos["entrada"] / UM_MILHAO
    custo_saida = Decimal(tokens_saida) * precos["saida"] / UM_MILHAO
    custo_total = custo_entrada + custo_saida

    return ResumoCusto(
        modelo=modelo,
        tokens_entrada=tokens_entrada,
        tokens_resposta=tokens_resposta,
        tokens_pensamento=tokens_pensamento,
        tokens_total=tokens_total,
        custo_entrada_usd=float(custo_entrada),
        custo_saida_usd=float(custo_saida),
        custo_total_usd=float(custo_total),
        disponivel=usage_metadata is not None and tokens_total > 0,
    )
