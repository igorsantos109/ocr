"""Tesseract real em imagem sintética em português (pula sem o binário)."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw, ImageFont
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.reconhecimento.base import RecognitionConfig
from ocr_historico.reconhecimento.tesseract_engine import TesseractEngine

runner = CliRunner()
TESSEACT = TesseractEngine()


def _imagem_pt(caminho) -> None:
    fonte = ImageFont.load_default(size=64)
    img = Image.new("RGB", (1800, 500), "white")
    desenho = ImageDraw.Draw(img)
    desenho.text((60, 60), "Presidente do Brasil", fill="black", font=fonte)
    desenho.text((60, 220), "Rio de Janeiro 1891", fill="black", font=fonte)
    img.save(caminho)


@pytest.mark.skipif(not TESSEACT.available(), reason="Tesseract ausente neste host")
class TestTesseractReal:
    def test_reconhece_portugues(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "pt.png"
        _imagem_pt(alvo)
        resultado = TESSEACT.recognize_page(alvo, RecognitionConfig(idioma="por", psm=6))
        assert resultado.texto_bruto.strip(), "Tesseract não devolveu texto"
        assert resultado.linhas, "Tesseract não devolveu linhas com caixas"

    def test_lote_cli_com_tesseract(self, diretorio_tmp) -> None:
        entrada = diretorio_tmp / "entrada"
        entrada.mkdir()
        _imagem_pt(entrada / "folha.png")
        cfg = diretorio_tmp / "config.yaml"
        cfg.write_text(
            f"perfil: impresso_moderno\nrender_dpi: 150\n"
            f"saida: {diretorio_tmp / 'saida'}\nbanco: {diretorio_tmp / 'b.sqlite3'}\n",
            encoding="utf-8",
        )
        resultado = runner.invoke(app, ["processar", str(entrada), "--config", str(cfg), "--engine", "tesseract"])
        assert resultado.exit_code == 0, resultado.output
        bruto = diretorio_tmp / "saida" / "folha" / "folha_bruto.txt"
        assert bruto.is_file()
        assert bruto.read_text(encoding="utf-8").strip()
