"""Diretório de motores: disponibilidade honesta com motivo (sem rede real)."""

from __future__ import annotations

import json

from ocr_historico.reconhecimento.factory import listar_motores


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


def test_vl_com_modelo_sem_visao_traz_motivo(monkeypatch) -> None:
    def _abrir(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/v1/models"):
            return _Resp(200, json.dumps({"data": [{"id": "llm-de-texto"}]}).encode())
        return _Resp(200, b"ok")

    monkeypatch.setattr("urllib.request.urlopen", _abrir)
    por_nome = {m["nome"]: m for m in listar_motores()}
    assert por_nome["paddle_vl"]["disponivel"] is False
    assert "visão" in str(por_nome["paddle_vl"]["motivo"])
    # sem servidor: fora do ar (aqui o fake cobre todas as URLs; força erro p/ 8082)
    assert por_nome["olmocr"]["disponivel"] is False


def test_usa_config_paddlevl_no_diretorio(monkeypatch) -> None:
    from ocr_historico.config import PaddleVLConfig

    def _abrir(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/v1/models"):
            return _Resp(200, json.dumps({"data": [{"id": "Meu-VL-7B"}]}).encode())
        return _Resp(200, b"ok")

    monkeypatch.setattr("urllib.request.urlopen", _abrir)

    class _Cfg:
        paddlevl = PaddleVLConfig(base_url="http://127.0.0.1:9999", model="Meu-VL-7B")
        olmocr = None

    por_nome = {m["nome"]: m for m in listar_motores(_Cfg())}
    assert por_nome["paddle_vl"]["disponivel"] is True
    assert por_nome["paddle_vl"]["endpoint"] == "http://127.0.0.1:9999"
    assert por_nome["paddle_vl"]["modelo"] == "Meu-VL-7B"


def test_sem_servidor_motivo_fora_do_ar(monkeypatch) -> None:
    import urllib.error

    def _abrir(req, timeout=None):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", _abrir)
    por_nome = {m["nome"]: m for m in listar_motores()}
    assert por_nome["paddle_vl"]["disponivel"] is False
    assert por_nome["olmocr"]["disponivel"] is False
    assert por_nome["paddle_vl"]["motivo"] == "servidor fora do ar"
    assert all({"nome", "disponivel", "motivo"} <= set(m) for m in por_nome.values())
