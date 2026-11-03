"""Testes do Marco 1: PDF textual, escaneado e renderização."""

from __future__ import annotations

import fitz

from ocr_historico.ingestao.pdf import dimensoes_pdf_px, info_pdf, renderizar_pagina


def _pdf_textual(caminho, paginas: int = 2):
    with fitz.open() as doc:
        for _ in range(paginas):
            pagina = doc.new_page()
            pagina.insert_text((72, 72), "Carta de 1891 ao presidente. " * 10)
        doc.save(caminho)


def _pdf_escaneado(caminho) -> None:
    with fitz.open() as doc:
        pagina = doc.new_page()
        pix = pagina.get_pixmap()
        pix.save(str(caminho) + ".png")
        pagina2 = doc.new_page()
        pagina2.insert_image(pagina2.rect, filename=str(caminho) + ".png")
        doc.save(caminho)


class TestPdf:
    def test_detecta_camada_textual(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "texto.pdf"
        _pdf_textual(alvo)
        info = info_pdf(alvo)
        assert info.paginas == 2
        assert info.tem_texto is True

    def test_escaneado_sem_texto(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "scan.pdf"
        _pdf_escaneado(alvo)
        info = info_pdf(alvo)
        assert info.tem_texto is False

    def test_renderiza_sem_modificar_original(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "texto.pdf"
        _pdf_textual(alvo, paginas=1)
        antes = alvo.read_bytes()
        saida = diretorio_tmp / "render" / "p0001.png"
        renderizar_pagina(alvo, 1, 150, saida)
        assert saida.is_file()
        assert alvo.read_bytes() == antes
        largura, altura = dimensoes_pdf_px(alvo, 150)[0]
        assert largura > 1000 and altura > 1000
