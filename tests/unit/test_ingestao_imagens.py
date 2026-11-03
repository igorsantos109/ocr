"""Testes do Marco 1: imagens e TIFF multipágina."""

from __future__ import annotations

from PIL import Image

from ocr_historico.ingestao.imagens import info_imagem


class TestImagens:
    def test_png_simples(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "foto.png"
        Image.new("RGB", (1200, 1600), "white").save(alvo)
        info = info_imagem(alvo)
        assert info.quadros == 1
        assert (info.largura, info.altura) == (1200, 1600)
        assert info.resolucao_baixa is False

    def test_tiff_multipagina_e_resolucao_baixa(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "carta.tif"
        quadros = [Image.new("RGB", (400, 500), "white") for _ in range(3)]
        quadros[0].save(alvo, save_all=True, append_images=quadros[1:])
        info = info_imagem(alvo)
        assert info.quadros == 3
        assert info.resolucao_baixa is True
