"""Testes do adaptador PaddleOCR sem instalar modelo ou pacote pesado."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ocr_historico.reconhecimento.base import RecognitionConfig
from ocr_historico.reconhecimento.paddle_engine import PaddleOCREngine


def test_paddleocr_normaliza_saida_legacy() -> None:
    engine = PaddleOCREngine()
    saida = [
        [
            [[[10, 20], [110, 20], [110, 50], [10, 50]], ("Brazil anno", 0.91)],
            [[[20, 70], [120, 70], [120, 100], [20, 100]], ("pharmacia", 0.84)],
        ]
    ]
    linhas = engine._extrair_linhas(saida, 1)
    assert [linha.texto for linha in linhas] == ["Brazil anno", "pharmacia"]
    assert (linhas[0].x, linhas[0].y, linhas[0].largura, linhas[0].altura) == (10, 20, 100, 30)
    assert linhas[0].confianca == 0.91


def test_paddleocr_indisponivel_tem_mensagem_acionavel(monkeypatch, tmp_path: Path) -> None:
    engine = PaddleOCREngine()
    monkeypatch.setattr(engine, "available", lambda: False)
    with pytest.raises(Exception, match="pip install paddleocr"):
        engine.recognize_page(tmp_path / "ausente.png", RecognitionConfig(engine="paddleocr"))


def test_paddleocr_mockado_executa_sem_download(monkeypatch, tmp_path: Path) -> None:
    imagem = tmp_path / "pagina.png"
    Image.new("RGB", (200, 100), "white").save(imagem)
    engine = PaddleOCREngine()
    monkeypatch.setattr(engine, "available", lambda: True)

    class FalsoPaddle:
        def ocr(self, caminho, cls=True):
            assert caminho == str(imagem)
            return [[[[[1, 2], [50, 2], [50, 20], [1, 20]], ("texto", 0.8)]]]

    monkeypatch.setattr(engine, "_carregar", lambda config: FalsoPaddle())
    resultado = engine.recognize_page(imagem, RecognitionConfig(engine="paddleocr"), numero_pagina=1)
    assert resultado.motor == "paddleocr"
    assert resultado.texto_bruto == "texto"
    assert resultado.linhas[0].confianca == 0.8


def test_paddleocr_onnx_real_cpu(tmp_path: Path, monkeypatch) -> None:
    """Smoke test do backend ONNX empacotado, sem baixar pesos."""
    pytest.importorskip("rapidocr_onnxruntime")
    imagem = tmp_path / "pagina.png"
    imagem_pil = Image.new("RGB", (1000, 300), "white")
    from PIL import ImageDraw

    ImageDraw.Draw(imagem_pil).text((30, 80), "Brazil anno pharmacia 1891", fill="black")
    imagem_pil.save(imagem)
    monkeypatch.setenv("OCRHIST_PADDLE_BACKEND", "onnx")
    resultado = PaddleOCREngine().recognize_page(
        imagem, RecognitionConfig(engine="paddleocr", backend="onnx")
    )
    assert "Brazil" in resultado.texto_bruto
    assert resultado.linhas and resultado.linhas[0].confianca is not None
