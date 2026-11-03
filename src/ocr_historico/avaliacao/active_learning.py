"""Seleção ativa de linhas para priorizar revisão humana."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from ..database import fabrica_sessoes, inicializar_banco
from ..models import Documento, Linha, Pagina


@dataclass(frozen=True)
class CandidatoRevisao:
    linha_id: str
    documento: str
    pagina: int
    numero: int
    confianca: float | None
    prioridade: str
    texto: str
    imagem: str | None
    pontuacao: float


def selecionar_linhas(
    banco: Path | str,
    limite: int = 100,
    incluir_revisadas: bool = False,
) -> list[CandidatoRevisao]:
    """Seleciona linhas por incerteza: ausência de confiança vem primeiro."""
    if limite < 1:
        raise ValueError("limite deve ser positivo")
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as sessao:
        consulta = (
            select(Linha, Pagina, Documento)
            .join(Pagina, Linha.pagina_id == Pagina.id)
            .join(Documento, Pagina.documento_id == Documento.id)
            .order_by(Linha.confianca.asc().nullsfirst(), Documento.nome_original, Pagina.numero, Linha.numero)
            .limit(limite)
        )
        if not incluir_revisadas:
            consulta = consulta.where(
                Linha.exige_revisao.is_(True),
                Linha.status_revisao.not_in(["revisada", "ilegivel", "treinamento"]),
            )
        resultados = sessao.execute(consulta).all()
    candidatos: list[CandidatoRevisao] = []
    for linha, pagina, documento in resultados:
        confianca = linha.confianca
        pontuacao = 1.0 if confianca is None else 1.0 - max(0.0, min(1.0, confianca))
        candidatos.append(
            CandidatoRevisao(
                linha_id=linha.id,
                documento=documento.nome_original,
                pagina=pagina.numero,
                numero=linha.numero,
                confianca=confianca,
                prioridade=linha.status_revisao,
                texto=linha.texto_diplomatico,
                imagem=linha.imagem_linha or pagina.imagem_pre_processada or pagina.imagem_original,
                pontuacao=round(pontuacao, 4),
            )
        )
    return candidatos
