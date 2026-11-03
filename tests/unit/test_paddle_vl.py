"""Testes do motor PaddleOCR-VL (servidor local, sem rede real)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from ocr_historico.reconhecimento.base import MotorIndisponivel, RecognitionConfig
from ocr_historico.reconhecimento.factory import criar_engine, motores_conhecidos
from ocr_historico.reconhecimento.paddle_vl_engine import (
    PaddleVLEngine,
    _conferir_modelo,
    _extrair_texto,
    _imagem_base64,
    _parece_vl,
)

VL_MODEL = "PaddlePaddle/PaddleOCR-VL-1.6"


class _Resp:
    def __init__(self, status: int = 200, corpo: bytes = b"ok") -> None:
        self.status = status
        self._corpo = corpo

    def read(self) -> bytes:
        return self._corpo

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _fake_urlopen(respostas: dict, registro: dict | None = None):
    def _abrir(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if registro is not None and hasattr(req, "data") and req.data:
            registro["corpo"] = req.data
        for sufixo, resp in respostas.items():
            if url.endswith(sufixo):
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise ConnectionError(f"URL inesperada: {url}")

    return _abrir


def _chat_ok(texto: str) -> _Resp:
    return _Resp(200, json.dumps({"choices": [{"message": {"content": texto}}]}).encode())


def _models(ids: list[str]) -> _Resp:
    return _Resp(200, json.dumps({"data": [{"id": i} for i in ids]}).encode())


def _cfg(**kwargs) -> RecognitionConfig:
    base = {"engine": "paddle_vl", "base_url": "http://127.0.0.1:8081", "timeout_segundos": 30}
    base.update(kwargs)
    return RecognitionConfig(**base)


def test_registrado_na_fabrica() -> None:
    assert "paddle_vl" in motores_conhecidos()
    assert criar_engine("paddle_vl").name == "paddle_vl"


def test_parece_vl() -> None:
    assert _parece_vl("PaddlePaddle/PaddleOCR-VL-1.6")
    assert _parece_vl("pp-ocrv5_server")
    assert _parece_vl("Qwen3VL-8B-Instruct")
    assert not _parece_vl("huihui-qwen3-8b-abliterated-v2")
    assert not _parece_vl("DeepSeek-R1-Distill-Llama-8B")


def test_extrair_texto_str_e_partes() -> None:
    assert _extrair_texto({"choices": [{"message": {"content": "  Olá 1891  "}}]}) == "Olá 1891"
    partes = [{"type": "text", "text": "linha1"}, {"type": "text", "text": "linha2"}]
    assert _extrair_texto({"choices": [{"message": {"content": partes}}]}) == "linha1\nlinha2"
    with pytest.raises(MotorIndisponivel):
        _extrair_texto({"sem": "choices"})


def test_imagem_base64_limita_lado(diretorio_tmp: Path) -> None:
    img = diretorio_tmp / "grande.png"
    Image.new("RGB", (3000, 4000), "white").save(img)
    b64, larg, alt = _imagem_base64(img, max_lado=2048)
    assert max(larg, alt) <= 2048
    assert len(b64) > 100


def test_ping_exige_resposta_2xx(monkeypatch) -> None:
    from ocr_historico.reconhecimento.paddle_vl_engine import _ping

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp(404, b"not found"))
    assert _ping("http://x") is False


def test_indisponivel_sem_servidor(monkeypatch) -> None:
    import urllib.error

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("down"))
    )
    motor = PaddleVLEngine()
    assert motor.available() is False
    assert motor.available_com_config(_cfg()) is False


def test_recusa_modelo_sem_visao(monkeypatch, diretorio_tmp: Path) -> None:
    img = diretorio_tmp / "p.png"
    Image.new("RGB", (100, 60), "white").save(img)
    respostas = {
        "/health": _Resp(200, b"ok"),
        "/v1/models": _models(["huihui-qwen3-8b-abliterated-v2"]),
    }
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(respostas))
    assert _conferir_modelo("http://x", VL_MODEL) is not None
    with pytest.raises(MotorIndisponivel, match="modelo inadequado"):
        PaddleVLEngine().recognize_page(img, _cfg())


def test_transcreve_pagina_como_bloco_unico(monkeypatch, diretorio_tmp: Path) -> None:
    img = diretorio_tmp / "p.png"
    Image.new("RGB", (400, 200), "white").save(img)
    registro: dict = {}
    respostas = {
        "/health": _Resp(200, b"ok"),
        "/v1/models": _models([VL_MODEL]),
        "/v1/chat/completions": _chat_ok("Illm. Snr. Presidente\nRio, 1891."),
    }
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(respostas, registro))
    res = PaddleVLEngine().recognize_page(img, _cfg())
    assert res.motor == "paddle_vl"
    assert res.texto_bruto == "Illm. Snr. Presidente\nRio, 1891."
    # sem caixas inventadas: linha única cobrindo a página, sem confiança
    assert len(res.linhas) == 1
    linha = res.linhas[0]
    assert (linha.x, linha.y) == (0, 0)
    assert (linha.largura, linha.altura) == (400, 200)
    assert linha.confianca is None
    assert res.confianca_media is None
    assert res.aviso is not None
    # prompt diplomático e imagem foram enviados
    corpo = json.loads(registro["corpo"])
    assert corpo["temperature"] == 0
    assert "grafia original" in corpo["messages"][0]["content"][0]["text"]


def test_transcricao_vazia_erro(monkeypatch, diretorio_tmp: Path) -> None:
    img = diretorio_tmp / "p.png"
    Image.new("RGB", (100, 60), "white").save(img)
    respostas = {
        "/health": _Resp(200, b"ok"),
        "/v1/models": _models([VL_MODEL]),
        "/v1/chat/completions": _chat_ok("   "),
    }
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(respostas))
    with pytest.raises(MotorIndisponivel, match="vazia"):
        PaddleVLEngine().recognize_page(img, _cfg())


def test_imagem_ausente_erro() -> None:
    with pytest.raises(MotorIndisponivel, match="não encontrada"):
        PaddleVLEngine().recognize_page("/inexistente/p.png", _cfg())


def test_recognize_lines_nao_suportado() -> None:
    with pytest.raises(NotImplementedError):
        PaddleVLEngine().recognize_lines([], _cfg())
