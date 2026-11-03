"""Conexão e inicialização idempotente do SQLite."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .models import Base


def criar_engine(caminho: Path | str) -> Engine:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{caminho.resolve()}", future=True)


_COLUNAS_OPCIONAIS = {
    "documentos": [
        ("origem_relativa", "TEXT"),
        ("tamanho_bytes", "INTEGER"),
        ("mtime_ns", "INTEGER"),
        ("original_preservado", "BOOLEAN DEFAULT 0"),
        ("preservado_path", "TEXT"),
        ("saida_relativa", "TEXT"),
    ],
    "paginas": [
        ("qualidade_json", "JSON"),
        ("preprocessamento_json", "JSON"),
        ("qualidade_score", "FLOAT"),
        ("qualidade_flags", "JSON"),
    ],
}


def migrar_banco(engine: Engine) -> None:
    """Migra bancos antigos de forma idempotente, preservando dados."""
    with engine.begin() as conexao:
        for tabela, colunas in _COLUNAS_OPCIONAIS.items():
            existentes = {col["name"] for col in inspect(engine).get_columns(tabela)}
            for nome, tipo in colunas:
                if nome not in existentes:
                    conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))


def inicializar_banco(caminho: Path | str) -> Engine:
    engine = criar_engine(caminho)
    Base.metadata.create_all(engine)
    try:
        migrar_banco(engine)
    except Exception:  # noqa: BLE001 - banco recém-criado não precisa migrar
        pass
    return engine


def fabrica_sessoes(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
