"""Testes das métricas de qualidade de página."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_historico.qualidade.metricas import avaliar_imagem


class TestMetricas:
    def test_branca_baixa_resolucao(self, diretorio_tmp: Path) -> None:
        alvo = diretorio_tmp / "branca.png"
        Image.new("RGB", (600, 800), "white").save(alvo)
        m = avaliar_imagem(alvo)
        assert m.largura == 600 and m.altura == 800
        assert m.baixa_resolucao is True
        assert m.muito_clara is True or m.paginas_vazias is True
        assert m.score is not None

    def test_png_normal(self, diretorio_tmp: Path) -> None:
        alvo = diretorio_tmp / "normal.png"
        imagem = Image.new("RGB", (1600, 2200), "white")
        for y in range(100, 2100, 120):
            imagem.paste("black", (100, y, 1500, y + 4))
        imagem.save(alvo)
        m = avaliar_imagem(alvo)
        assert "baixa_resolucao" not in m.flags

    def test_dpi_informado(self, diretorio_tmp: Path) -> None:
        alvo = diretorio_tmp / "dpi.png"
        Image.new("RGB", (1200, 1600), "white").save(alvo, dpi=(300, 300))
        m = avaliar_imagem(alvo)
        assert m.dpi == 300