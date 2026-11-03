"""Smoke test da GUI real em um navegador headless.

O teste é opcional: requer o extra ``.[gui]`` e um Chromium/Chrome disponível.
Os testes HTTP continuam cobrindo a API mesmo em ambientes sem navegador.
"""

from __future__ import annotations

import shutil
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.models import Documento, Linha, Pagina
from ocr_historico.web.app import Manipulador

pytestmark = pytest.mark.gui


def _banco(tmp_path: Path) -> Path:
    banco = tmp_path / "gui.sqlite3"
    imagem = tmp_path / "pagina.png"
    Image.new("RGB", (400, 200), "white").save(imagem)
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as sessao:
        documento = Documento(
            id="doc-gui",
            caminho_original="/documento.png",
            nome_original="documento.png",
            sha256="f" * 64,
            tipo_arquivo="png",
            perfil="automatico",
            numero_paginas=1,
            status="concluido",
            configuracao_json={},
        )
        pagina = Pagina(
            id="pag-gui",
            documento=documento,
            numero=1,
            imagem_original=str(imagem),
            imagem_pre_processada=str(imagem),
            largura=400,
            altura=200,
            status="concluida",
        )
        sessao.add(documento)
        sessao.flush()
        sessao.add(
            Linha(
                id="linha-gui",
                pagina=pagina,
                numero=1,
                x=10,
                y=10,
                largura=200,
                altura=30,
                texto_bruto="Presldente 1891",
                texto_diplomatico="Presldente 1891",
                texto_normalizado="Presidente 1891",
                confianca=0.6,
                exige_revisao=True,
                status_revisao="alta",
            )
        )
        sessao.commit()
    return banco


@pytest.fixture
def servidor_gui(tmp_path: Path):
    Manipulador.banco = _banco(tmp_path)
    Manipulador.config_llm = {"enabled": False, "model": "", "base_url": "", "timeout": 5}
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        servidor.server_close()


@pytest.fixture
def pagina_navegador():
    playwright = pytest.importorskip("playwright.sync_api", reason="instale o extra .[gui]")
    executavel = next(
        (shutil.which(nome) for nome in ("google-chrome", "chromium", "chromium-browser") if shutil.which(nome)),
        None,
    )
    with playwright.sync_playwright() as api:
        opcoes = {"headless": True}
        if executavel:
            opcoes["executable_path"] = executavel
        try:
            navegador = api.chromium.launch(**opcoes)
        except Exception as erro:  # pragma: no cover - depende do host de CI
            pytest.skip(f"Chromium/Chrome indisponível para o teste da GUI: {erro}")
        pagina = navegador.new_page()
        try:
            yield pagina
        finally:
            navegador.close()


def test_fluxo_principal_da_gui_no_navegador(pagina_navegador, servidor_gui) -> None:
    pagina = pagina_navegador
    pagina.goto(servidor_gui + "/", wait_until="networkidle")

    assert pagina.title() == "OCR STUDIO V1 — estação de revisão local"
    pagina.locator("#lista-docs .doc").first.wait_for()
    pagina.locator("#lista-docs .doc").first.click(force=True)
    pagina.locator("#view-doc:not([hidden])").wait_for()

    pagina.locator('#faixa [data-pag="pag-gui"]').click(force=True)
    pagina.locator("#visor-dentro img").wait_for()
    pagina.locator("#tab-linha #ed-diplo").fill("Presidente 1891")
    with pagina.expect_response(lambda resposta: "/api/corrigir" in resposta.url and resposta.request.method == "POST"):
        pagina.locator("#btn-salvar").click(force=True)
    pagina.locator("#toasts").filter(has_text="Salvo e marcado como revisada.").wait_for()

    pagina.locator("#camada").select_option("original")
    assert "tipo=original" in pagina.locator("#visor-dentro img").get_attribute("src")


def test_gui_responde_em_viewport_mobile(pagina_navegador, servidor_gui) -> None:
    pagina = pagina_navegador
    pagina.set_viewport_size({"width": 390, "height": 844})
    pagina.goto(servidor_gui + "/", wait_until="networkidle")
    assert pagina.locator("#busca").is_visible()
    assert pagina.locator("#btnEnviar").is_visible()
    assert pagina.locator("#enginePanel").is_visible()
