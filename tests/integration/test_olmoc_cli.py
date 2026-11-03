"""Integração olmOCR: pipeline com servidor simulado + CLI + diagnóstico."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.config import AppConfig

runner = CliRunner()
OLM_MODEL = "Qwen3VL-8B-Instruct"


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


def _simular_vl(monkeypatch, texto: str = "Carta de 1891.") -> None:
    def _abrir(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/v1/chat/completions"):
            corpo = json.dumps({"choices": [{"message": {"content": texto}}]}).encode()
            return _Resp(200, corpo)
        if url.endswith("/v1/models"):
            corpo = json.dumps({"data": [{"id": OLM_MODEL}]}).encode()
            return _Resp(200, corpo)
        return _Resp(200, b"ok")

    monkeypatch.setattr("urllib.request.urlopen", _abrir)


def test_processar_olmocr_fim_a_fim(tmp_path: Path, monkeypatch) -> None:
    from sqlalchemy import select

    from ocr_historico.database import fabrica_sessoes, inicializar_banco
    from ocr_historico.ingestao import ingerir_entrada
    from ocr_historico.models import Documento
    from ocr_historico.pipeline import processar_documentos

    _simular_vl(monkeypatch, "Illm. Snr. Presidente\n1891.")
    entrada = tmp_path / "entrada"
    saida = tmp_path / "saida"
    entrada.mkdir()
    saida.mkdir()
    Image.new("RGB", (400, 200), "white").save(entrada / "carta.png")
    cfg = AppConfig(entrada=entrada, saida=saida, banco=tmp_path / "banco.sqlite3")
    assert ingerir_entrada(entrada, cfg).novos == 1
    resumo = processar_documentos(cfg, engine_nome="olmocr")
    assert resumo.paginas_ok == 1
    # bloco único, sem confiança → revisão alta; diplomático preserva grafia
    engine = inicializar_banco(cfg.banco)
    with fabrica_sessoes(engine)() as s:
        from ocr_historico.models import Linha

        linhas = s.scalars(select(Linha)).all()
        assert len(linhas) == 1
        assert linhas[0].texto_diplomatico == "Illm. Snr. Presidente\n1891."
        assert linhas[0].confianca is None
        assert linhas[0].exige_revisao is True
        doc = s.scalars(select(Documento)).one()
        assert doc.status == "concluido"
    # PAGE-XML e pasta de saída gerados sem repetir OCR
    assert (saida / "carta" / "carta_page.xml").is_file()


def test_processar_olmocr_servidor_errado_marca_erro(tmp_path: Path, monkeypatch) -> None:
    from ocr_historico.ingestao import ingerir_entrada
    from ocr_historico.pipeline import processar_documentos

    def _abrir(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/v1/models"):
            corpo = json.dumps({"data": [{"id": "modelo-de-texto-qualquer"}]}).encode()
            return _Resp(200, corpo)
        return _Resp(200, b"ok")

    monkeypatch.setattr("urllib.request.urlopen", _abrir)
    entrada = tmp_path / "entrada"
    saida = tmp_path / "saida"
    entrada.mkdir()
    saida.mkdir()
    Image.new("RGB", (100, 60), "white").save(entrada / "carta.png")
    cfg = AppConfig(entrada=entrada, saida=saida, banco=tmp_path / "banco.sqlite3")
    ingerir_entrada(entrada, cfg)
    resumo = processar_documentos(cfg, engine_nome="olmocr")
    assert resumo.paginas_ok == 0 and resumo.paginas_erro == 1


def test_cli_processar_aceita_olmocr() -> None:
    res = runner.invoke(app, ["processar", "--help"])
    assert res.exit_code == 0
    assert "olmocr" in res.output


def test_diagnostico_mostra_olmocr(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(f"banco: {tmp_path / 'd.sqlite3'}\n", encoding="utf-8")
    res = runner.invoke(app, ["diagnosticar", "--config", str(cfg)])
    assert res.exit_code == 0
    assert "olmOCR:" in res.stdout


def test_config_olmocr_yaml() -> None:
    from ocr_historico.config import carregar_config

    cfg = carregar_config(Path("configs/olmocr.yaml"))
    assert cfg.reconhecimento.engine == "olmocr"
    assert cfg.olmocr.base_url == "http://127.0.0.1:8082"
    assert cfg.olmocr.model == OLM_MODEL
