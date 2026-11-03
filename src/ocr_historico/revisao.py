"""Serviços de revisão humana e trilha de auditoria do Marco 4."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from .database import fabrica_sessoes, inicializar_banco
from .models import Correcao, Documento, Linha, Pagina, agora

STATUS_REVISAO = frozenset({"pendente", "alta", "média", "baixa", "revisada", "ilegivel", "treinamento"})
ORIGENS = frozenset({"humana", "regra", "llm_sugerido"})


@dataclass(frozen=True)
class ItemRevisao:
    linha_id: str
    documento_id: str
    documento: str
    pagina: int
    numero: int
    texto_bruto: str
    texto_diplomatico: str
    texto_normalizado: str | None
    confianca: float | None
    status: str
    prioridade: str
    imagem: str | None


def listar_fila(
    banco: Path | str,
    status: str | None = None,
    limite: int = 100,
) -> list[ItemRevisao]:
    """Lista linhas que exigem revisão, priorizando confiança menor."""
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
        if status:
            if status not in STATUS_REVISAO:
                raise ValueError(f"Status de revisão inválido: {status}")
            consulta = consulta.where(Linha.status_revisao == status)
        else:
            consulta = consulta.where(Linha.exige_revisao.is_(True))
        resultados = sessao.execute(consulta).all()
        return [
            ItemRevisao(
                linha_id=linha.id,
                documento_id=documento.id,
                documento=documento.nome_original,
                pagina=pagina.numero,
                numero=linha.numero,
                texto_bruto=linha.texto_bruto,
                texto_diplomatico=linha.texto_diplomatico,
                texto_normalizado=linha.texto_normalizado,
                confianca=linha.confianca,
                status=linha.status_revisao,
                prioridade=linha.status_revisao,
                imagem=linha.imagem_linha or pagina.imagem_pre_processada or pagina.imagem_original,
            )
            for linha, pagina, documento in resultados
        ]


def corrigir_linha(
    banco: Path | str,
    linha_id: str,
    texto_corrigido: str,
    origem: str = "humana",
    usuario: str | None = None,
    observacao: str | None = None,
    marcar_revisada: bool = True,
) -> Correcao:
    """Salva correção e atualiza apenas o texto diplomático, sempre auditando."""
    if origem not in ORIGENS:
        raise ValueError(f"Origem inválida: {origem}; use {sorted(ORIGENS)}")
    if not texto_corrigido.strip() and origem == "humana":
        raise ValueError("texto_corrigido não pode ser vazio para correção humana")
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as sessao:
        linha = sessao.get(Linha, linha_id)
        if linha is None:
            raise ValueError(f"Linha não encontrada: {linha_id}")
        anterior = linha.texto_diplomatico
        correcao = Correcao(
            id=uuid.uuid4().hex,
            linha_id=linha_id,
            texto_anterior=anterior,
            texto_corrigido=texto_corrigido,
            tipo_correcao="texto_diplomatico",
            origem=origem,
            usuario=usuario,
            observacao=observacao,
            criado_em=agora(),
        )
        sessao.add(correcao)
        linha.texto_diplomatico = texto_corrigido
        if marcar_revisada:
            linha.status_revisao = "revisada"
            linha.exige_revisao = False
        sessao.commit()
        return correcao


def marcar_linha(
    banco: Path | str,
    linha_id: str,
    status: str,
    usuario: str | None = None,
    observacao: str | None = None,
) -> Linha:
    """Marca uma linha como revisada, ilegível ou apta para treinamento."""
    if status not in {"revisada", "ilegivel", "treinamento", "pendente"}:
        raise ValueError("Status permitido: revisada, ilegivel, treinamento ou pendente")
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as sessao:
        linha = sessao.get(Linha, linha_id)
        if linha is None:
            raise ValueError(f"Linha não encontrada: {linha_id}")
        status_anterior = linha.status_revisao
        linha.status_revisao = status
        linha.exige_revisao = status not in {"revisada", "ilegivel", "treinamento"}
        if status_anterior != status or observacao:
            sessao.add(
                Correcao(
                    id=uuid.uuid4().hex,
                    linha_id=linha_id,
                    texto_anterior=linha.texto_diplomatico,
                    texto_corrigido=linha.texto_diplomatico,
                    tipo_correcao="status_revisao",
                    origem="humana",
                    usuario=usuario,
                    observacao=observacao or f"status: {status_anterior} -> {status}",
                    criado_em=agora(),
                )
            )
        sessao.commit()
        return linha
