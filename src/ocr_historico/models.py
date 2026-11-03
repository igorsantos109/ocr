"""Modelos SQLAlchemy do núcleo auditável.

O Marco 0 cria o esquema completo mínimo para que os próximos marcos possam
registrar ingestão, páginas, linhas, execuções e correções sem migração destrutiva.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def agora() -> datetime:
    return datetime.now().astimezone()


class Documento(Base):
    __tablename__ = "documentos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    caminho_original: Mapped[str] = mapped_column(Text, nullable=False)
    nome_original: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tipo_arquivo: Mapped[str] = mapped_column(String(32), nullable=False)
    perfil: Mapped[str] = mapped_column(String(64), nullable=False, default="automatico")
    numero_paginas: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pendente")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)
    configuracao_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem_relativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    tamanho_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mtime_ns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_preservado: Mapped[bool] = mapped_column(Boolean, default=False)
    preservado_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    saida_relativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    paginas: Mapped[list[Pagina]] = relationship(back_populates="documento", cascade="all, delete-orphan")
    execucoes: Mapped[list[Execucao]] = relationship(back_populates="documento", cascade="all, delete-orphan")


class Pagina(Base):
    __tablename__ = "paginas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    documento_id: Mapped[str] = mapped_column(ForeignKey("documentos.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    imagem_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    imagem_pre_processada: Mapped[str | None] = mapped_column(Text, nullable=True)
    largura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    altura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inclinacao: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitidez: Mapped[float | None] = mapped_column(Float, nullable=True)
    contraste: Mapped[float | None] = mapped_column(Float, nullable=True)
    classificacao: Mapped[str] = mapped_column(String(64), nullable=False, default="não classificada")
    qualidade_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    preprocessamento_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    qualidade_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualidade_flags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ordem_processamento: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pendente")
    documento: Mapped[Documento] = relationship(back_populates="paginas")
    regioes: Mapped[list[Regiao]] = relationship(back_populates="pagina", cascade="all, delete-orphan")
    linhas: Mapped[list[Linha]] = relationship(back_populates="pagina", cascade="all, delete-orphan")


class Regiao(Base):
    __tablename__ = "regioes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pagina_id: Mapped[str] = mapped_column(ForeignKey("paginas.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(64), default="texto")
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    largura: Mapped[int] = mapped_column(Integer, default=0)
    altura: Mapped[int] = mapped_column(Integer, default=0)
    ordem_leitura: Mapped[int] = mapped_column(Integer, default=0)
    pagina: Mapped[Pagina] = relationship(back_populates="regioes")


class Linha(Base):
    __tablename__ = "linhas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pagina_id: Mapped[str] = mapped_column(ForeignKey("paginas.id"), index=True)
    regiao_id: Mapped[str | None] = mapped_column(ForeignKey("regioes.id"), nullable=True)
    numero: Mapped[int] = mapped_column(Integer, default=1)
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    largura: Mapped[int] = mapped_column(Integer, default=0)
    altura: Mapped[int] = mapped_column(Integer, default=0)
    imagem_linha: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto_bruto: Mapped[str] = mapped_column(Text, default="")
    texto_diplomatico: Mapped[str] = mapped_column(Text, default="")
    texto_normalizado: Mapped[str | None] = mapped_column(Text, nullable=True)
    confianca: Mapped[float | None] = mapped_column(Float, nullable=True)
    exige_revisao: Mapped[bool] = mapped_column(Boolean, default=True)
    status_revisao: Mapped[str] = mapped_column(String(32), default="pendente")
    pagina: Mapped[Pagina] = relationship(back_populates="linhas")


class Execucao(Base):
    __tablename__ = "execucoes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    documento_id: Mapped[str] = mapped_column(ForeignKey("documentos.id"), index=True)
    motor: Mapped[str] = mapped_column(String(64), nullable=False)
    versao_modelo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    etapa: Mapped[str] = mapped_column(String(64), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="iniciada")
    parametros_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    documento: Mapped[Documento] = relationship(back_populates="execucoes")


class Correcao(Base):
    __tablename__ = "correcoes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    linha_id: Mapped[str] = mapped_column(ForeignKey("linhas.id"), index=True)
    texto_anterior: Mapped[str] = mapped_column(Text, nullable=False)
    texto_corrigido: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_correcao: Mapped[str] = mapped_column(String(64), nullable=False)
    origem: Mapped[str] = mapped_column(String(32), nullable=False)
    usuario: Mapped[str | None] = mapped_column(String(128), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
