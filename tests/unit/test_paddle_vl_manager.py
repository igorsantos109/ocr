from __future__ import annotations

from pathlib import Path

from ocr_historico.config import AppConfig
from ocr_historico.web.paddle_vl import PaddleVLManager


def test_status_informa_configuracao_e_nao_inicia_servidor(tmp_path: Path, monkeypatch) -> None:
    gerente = PaddleVLManager(tmp_path)
    cfg = AppConfig(banco=tmp_path / "banco.sqlite3")
    monkeypatch.setattr(gerente, "_online", lambda base: (False, []))

    estado = gerente.status(cfg)

    assert estado["online"] is False
    assert estado["gerenciado"] is False
    assert estado["endpoint"] == "http://127.0.0.1:8082"
    assert estado["modelo"] == "Qwen3VL-8B-Instruct"
    assert estado["pode_iniciar"] is False


def test_status_olmocr_usa_modelo_e_mensagem_proprios(monkeypatch, tmp_path: Path) -> None:
    gerente = PaddleVLManager(tmp_path)
    cfg = AppConfig(banco=tmp_path / "banco.sqlite3")
    monkeypatch.setattr(gerente, "_online", lambda base: (True, ["olmOCR-2-7B"]))

    estado = gerente.status(cfg, "olmocr")

    assert estado["motor"] == "olmocr"
    assert estado["modelo"] == "Qwen3VL-8B-Instruct"
    assert "olmocr" in str(estado["mensagem"])
    assert gerente._script_for(cfg, "olmocr").name == "servidor_qwen3vl.sh"


def test_status_reconhece_modelo_visual(monkeypatch, tmp_path: Path) -> None:
    gerente = PaddleVLManager(tmp_path)
    cfg = AppConfig(banco=tmp_path / "banco.sqlite3")
    monkeypatch.setattr(gerente, "_online", lambda base: (True, ["Qwen3VL-8B-Instruct"]))

    estado = gerente.status(cfg)

    assert estado["online"] is True
    assert estado["modelos"] == ["Qwen3VL-8B-Instruct"]
    assert estado["modelo_visual"] is True
    assert "pronto" in str(estado["mensagem"])
