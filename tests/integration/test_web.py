"""Integração da GUI local: rotas, filtros e política de bind."""

from __future__ import annotations

import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from PIL import Image

from ocr_historico.config import AppConfig
from ocr_historico.ingestao.servico import ingerir_entrada
from ocr_historico.web.app import Manipulador, servir


def _servidor_teste(banco):
    Manipulador.banco = banco
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    return servidor


def _get(servidor, caminho: str):
    url = f"http://127.0.0.1:{servidor.server_port}{caminho}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


class TestWeb:
    def test_painel_responsivo_e_api(self, diretorio_tmp) -> None:
        entrada = diretorio_tmp / "entrada"
        entrada.mkdir()
        Image.new("RGB", (1200, 1600), "white").save(entrada / "carta.png")
        config = AppConfig(
            entrada=entrada,
            saida=diretorio_tmp / "saida",
            banco=diretorio_tmp / "b.sqlite3",
        )
        ingerir_entrada(entrada, config)
        servidor = _servidor_teste(diretorio_tmp / "b.sqlite3")
        try:
            codigo, html = _get(servidor, "/")
            assert codigo == 200
            assert 'name="viewport"' in html
            assert "/api/documentos" in html

            codigo, corpo = _get(servidor, "/api/documentos")
            assert codigo == 200
            assert "carta.png" in corpo

            codigo, corpo = _get(servidor, "/api/documentos?status=erro")
            assert codigo == 200
            assert "carta.png" not in corpo

            codigo, corpo = _get(servidor, "/api/documentos?busca=carta")
            assert codigo == 200
            assert "carta.png" in corpo
        finally:
            servidor.shutdown()
            servidor.server_close()

    def test_recusa_bind_externo_sem_flag(self, diretorio_tmp) -> None:
        config = AppConfig(
            entrada=diretorio_tmp,
            saida=diretorio_tmp,
            banco=diretorio_tmp / "b.sqlite3",
        )
        with pytest.raises(ValueError, match="expor-rede"):
            servir(config, host="0.0.0.0", porta=0)
