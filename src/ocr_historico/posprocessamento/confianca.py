"""Pontuação conservadora e prioridade da fila de revisão."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AvaliacaoConfianca:
    confianca: float | None
    prioridade: str
    exige_revisao: bool
    motivos: tuple[str, ...]


def calcular_confianca(
    motor: float | None,
    nitidez: float | None = None,
    contraste: float | None = None,
    texto: str = "",
    divergente: bool = False,
) -> float | None:
    """Combina sinais sem transformar dicionário em prova de correção.

    O motor é o sinal principal; qualidade e anomalias apenas reduzem o
    resultado. A função mantém `None` quando não existe confiança do motor.
    """
    if motor is None:
        return None
    score = max(0.0, min(1.0, motor))
    if nitidez is not None and nitidez < 20:
        score -= 0.08
    if contraste is not None and contraste < 20:
        score -= 0.05
    if divergente:
        score -= 0.10
    if texto:
        anormais = len(re.findall(r"[^\w\sÀ-ÿ.,;:!?()\-/'\"“”]", texto, flags=re.UNICODE))
        if anormais / max(1, len(texto)) > 0.08:
            score -= 0.08
    return round(max(0.0, min(1.0, score)), 4)


def classificar_revisao(
    confianca: float | None,
    limiar_alta: float = 0.70,
    limiar_revisao: float = 0.82,
    falha_segmentacao: bool = False,
) -> AvaliacaoConfianca:
    motivos: list[str] = []
    if falha_segmentacao:
        motivos.append("falha de segmentação")
    if confianca is None:
        motivos.append("motor sem confiança")
        return AvaliacaoConfianca(None, "alta", True, tuple(motivos))
    if confianca < limiar_alta:
        motivos.append("confiança abaixo de 0,70")
        return AvaliacaoConfianca(confianca, "alta", True, tuple(motivos))
    if confianca < limiar_revisao:
        motivos.append("confiança abaixo do limiar de revisão")
        return AvaliacaoConfianca(confianca, "média", True, tuple(motivos))
    if falha_segmentacao:
        return AvaliacaoConfianca(confianca, "alta", True, tuple(motivos))
    return AvaliacaoConfianca(confianca, "baixa", False, tuple(motivos))
