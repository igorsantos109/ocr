"""Testes do motor deepseek_ocr2 (sem rede, sem servidor)."""

from __future__ import annotations

import base64
import json
import urllib.error
from pathlib import Path

import pytest
from PIL import Image

from ocr_historico.reconhecimento.base import MotorIndisponivel, RecognitionConfig
from ocr_historico.reconhecimento.deepseekocr2_engine import (
    DeepSeekOCR2Engine,
    _conferir_modelo,
    _extrair_texto,
    _imagem_base64,
    _modelo,
    _parece_vl,
    _url,
)
from ocr_historico.reconhecimento.factory import criar_engine, motores_conhecidos


def _cfg(**kwargs):
    base = {"engine": "deepseek_ocr2", "base_url": "http://127.0.0.1:9", "modelo": "DeepSeek-OCR-2"}
    base.update(kwargs)
    return RecognitionConfig(**base)


def _resposta(texto: str) -> dict:
    return {"choices": [{"message": {"content": texto}}]}


class _Resp:
    def __init__(self, dados: dict):
        self._dados = dados
        self.status = 200

    def read(self) -> bytes:
        return json.dumps(self._dados).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_registrado_na_factory():
    assert "deepseek_ocr2" in motores_conhecidos()
    assert isinstance(criar_engine("deepseek_ocr2"), DeepSeekOCR2Engine)


def test_parece_vl():
    assert _parece_vl("DeepSeek-OCR-2")
    assert _parece_vl("deepseek-ocr-2-Q4_K_M")
    assert _parece_vl("Qwen3VL-8B-Instruct")
    assert not _parece_vl("Huihui-Qwen3-8B-abliterated")
    assert not _parece_vl("tesseract-por")


def test_url_modelo_padrao():
    assert _url(RecognitionConfig(engine="deepseek_ocr2")) == "http://127.0.0.1:8084"
    assert _modelo(RecognitionConfig(engine="deepseek_ocr2")) == "DeepSeek-OCR-2"
    assert _modelo(_cfg(modelo="best")) == "DeepSeek-OCR-2"


def test_extrair_texto():
    assert _extrair_texto(_resposta("  olá  ")) == "olá"
    with pytest.raises(MotorIndisponivel):
        _extrair_texto({})


def test_imagem_base64_limita_lado(tmp_path: Path):
    img = Image.new("RGB", (3000, 100), "white")
    caminho = tmp_path / "g.png"
    img.save(caminho)
    b64, larg, alt = _imagem_base64(caminho, max_lado=1540)
    assert larg <= 1540 and alt <= 1540
    assert base64.b64decode(b64)


def test_indisponivel_sem_servidor(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("down")))
    motor = DeepSeekOCR2Engine()
    assert motor.available() is False
    assert motor.available_com_config(_cfg()) is False
    with pytest.raises(MotorIndisponivel):
        motor.recognize_page("/tmp/x.png", _cfg())


def test_recusa_modelo_sem_visao(monkeypatch):
    dados = {"data": [{"id": "Huihui-Qwen3-8B-abliterated"}]}
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp(dados))
    assert _conferir_modelo("http://x", "DeepSeek-OCR-2") is not None
    with pytest.raises(MotorIndisponivel):
        DeepSeekOCR2Engine().recognize_page("/tmp/x.png", _cfg(base_url="http://x"))


def test_transcreve_um_bloco(tmp_path: Path, monkeypatch):
    img = Image.new("RGB", (200, 60), "white")
    caminho = tmp_path / "p.png"
    img.save(caminho)
    chamadas: list[dict] = []

    def fake(req, *a, **k):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/v1/models") or getattr(req, "data", None) is None:
            return _Resp({"data": [{"id": "DeepSeek-OCR-2"}]})
        chamadas.append(json.loads(req.data.decode()))
        return _Resp(_resposta("# Carta\n\ntexto"))

    monkeypatch.setattr("urllib.request.urlopen", fake)
    res = DeepSeekOCR2Engine().recognize_page(caminho, _cfg(base_url="http://x"))
    assert res.texto_bruto == "# Carta\n\ntexto"
    assert len(res.linhas) == 1 and res.linhas[0].confianca is None
    assert res.aviso
    prompt = chamadas[0]["messages"][0]["content"][0]["text"]
    assert "<|grounding|>" in prompt
