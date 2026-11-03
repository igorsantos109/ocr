"""Testes do Marco 0: esquema e criação idempotente do banco."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect

from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.models import Documento, Pagina

TABLAS = {
    "documentos",
    "paginas",
    "regioes",
    "linhas",
    "execucoes",
    "correcoes",
}


class TestBancoIdempotente:
    def test_crea_mas_no_duplica(self, diretorio_tmp: Path) -> None:
        ruta = diretorio_tmp / "ocr_historico.sqlite3"
        inicializar_banco(ruta)
        inicializar_banco(ruta)
        names = set(inspect(inicializar_banco(ruta)).get_table_names())
        assert TABLAS.issubset(names)

    def test_registra_documento_y_paginas(self, diretorio_tmp: Path) -> None:
        engine = inicializar_banco(diretorio_tmp / "banco.sqlite3")
        sesion = fabrica_sessoes(engine)()
        doc = Documento(
            id="doc-1",
            caminho_original="/tmp/carta.pdf",
            nome_original="carta.pdf",
            sha256="a" * 64,
            tipo_arquivo="pdf",
            perfil="automatico",
            status="pendente",
            configuracao_json={"render_dpi": 300},
        )
        Pagina(id="pag-1", documento=doc, numero=1, dpi=300, status="pendente")
        sesion.add(doc)
        sesion.commit()

        recargado = sesion.get(Documento, "doc-1")
        assert recargado is not None
        assert recargado.sha256 == "a" * 64
        assert recargado.criado_em is not None and isinstance(recargado.criado_em, datetime)
        assert [p.numero for p in recargado.paginas] == [1]
        sesion.close()
