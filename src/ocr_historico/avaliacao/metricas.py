"""CER/WER sem dependência externa, com operações de edição."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ResultadoMetrica:
    valor: float
    distancia: int
    referencia: int
    insercoes: int
    delecoes: int
    substituicoes: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "valor": self.valor,
            "distancia": self.distancia,
            "referencia": self.referencia,
            "insercoes": self.insercoes,
            "delecoes": self.delecoes,
            "substituicoes": self.substituicoes,
        }


def _editar(referencia: Sequence[T], hipotese: Sequence[T]) -> ResultadoMetrica:
    n, m = len(referencia), len(hipotese)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    operacoes: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
        operacoes[i][0] = "deleção"
    for j in range(1, m + 1):
        dp[0][j] = j
        operacoes[0][j] = "inserção"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if referencia[i - 1] == hipotese[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
                operacoes[i][j] = "igual"
            else:
                custos = {
                    "deleção": dp[i - 1][j] + 1,
                    "inserção": dp[i][j - 1] + 1,
                    "substituição": dp[i - 1][j - 1] + 1,
                }
                op = min(custos, key=lambda chave: custos[chave])
                dp[i][j] = custos[op]
                operacoes[i][j] = op
    i, j = n, m
    contagem = {"inserção": 0, "deleção": 0, "substituição": 0}
    while i > 0 or j > 0:
        op = operacoes[i][j] or "substituição"
        if op == "igual":
            i -= 1
            j -= 1
        elif op == "deleção":
            contagem["deleção"] += 1
            i -= 1
        elif op == "inserção":
            contagem["inserção"] += 1
            j -= 1
        else:
            contagem["substituição"] += 1
            i -= 1
            j -= 1
    return ResultadoMetrica(
        valor=dp[n][m] / n if n else (0.0 if not m else 1.0),
        distancia=dp[n][m],
        referencia=n,
        insercoes=contagem["inserção"],
        delecoes=contagem["deleção"],
        substituicoes=contagem["substituição"],
    )


def _sem_normalizacao(texto: str) -> str:
    return texto


def _normalizar_simples(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.strip().lower())


def calcular_cer(
    referencia: str,
    hipotese: str,
    normalizar: bool = False,
    normalizador: Callable[[str], str] | None = None,
) -> ResultadoMetrica:
    fn = normalizador or (_normalizar_simples if normalizar else _sem_normalizacao)
    return _editar(list(fn(referencia)), list(fn(hipotese)))


def calcular_wer(
    referencia: str,
    hipotese: str,
    normalizar: bool = False,
    normalizador: Callable[[str], str] | None = None,
) -> ResultadoMetrica:
    fn = normalizador or (_normalizar_simples if normalizar else _sem_normalizacao)
    return _editar(fn(referencia).split(), fn(hipotese).split())
