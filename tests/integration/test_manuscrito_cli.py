"""Integração Marco 5: CLI treinar kraken, diagnostico e fallback manuscrito."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.config import AppConfig

runner = CliRunner()


def test_treinar_kraken_help() -> None:
    res = runner.invoke(app, ["treinar", "kraken", "--help"])
    assert res.exit_code == 0
    assert "kraken" in res.stdout.lower()


def test_treinar_kraken_dry_run_dataset_minimo(tmp_path: Path) -> None:
    base = tmp_path / "ground_truth"
    base.mkdir(parents=True)
    (base / "imagens").mkdir()
    (base / "transcricoes").mkdir()
    img = Image.new("RGB", (60, 20), color="white")
    img.save(base / "imagens" / "carta_001_p001_l001.png")
    (base / "transcricoes" / "carta_001_p001_l001.gt.txt").write_text("test 1891", encoding="utf-8")
    (base / "manifest.jsonl").write_text(
        json.dumps(
            {
                "id": "carta_001_p001_l001",
                "imagem": "imagens/carta_001_p001_l001.png",
                "transcricao": "transcricoes/carta_001_p001_l001.gt.txt",
                "documento": "carta_001",
                "pagina": 1,
                "escrevente": "a",
                "periodo": "1891",
                "revisado": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    res = runner.invoke(app, ["treinar", "kraken", str(base), "--dry-run", "--epocas", "2"])
    assert res.exit_code == 0, res.stdout + res.stderr
    assert "Comando:" in res.stdout
    assert "Saída:" in res.stdout


def test_diagnostico_mostra_kraken(tmp_path: Path) -> None:
    cfg = AppConfig(banco=tmp_path / "diag.sqlite3")
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(f"banco: {cfg.banco}\n", encoding="utf-8")
    res = runner.invoke(app, ["diagnosticar", "--config", str(cfg_path)])
    assert res.exit_code == 0
    assert "Kraken:" in res.stdout


def test_processar_manuscrito_fallback_para_tesseract(tmp_path: Path, monkeypatch) -> None:
    # cria imagem simples e processa com perfil manuscrito (kraken indisponível → fallback tesseract)
    from ocr_historico.config import AppConfig
    from ocr_historico.ingestao import ingerir_entrada
    from ocr_historico.pipeline import processar_documentos
    from ocr_historico.reconhecimento.base import LinhaRec, ResultadoPagina
    from ocr_historico.reconhecimento.tesseract_engine import TesseractEngine

    # fake tesseract disponível
    def fake_available(self) -> bool:
        return True

    def fake_recognize(self, image_path, config, numero_pagina=1):
        return ResultadoPagina(
            texto_bruto="linha manuscrita 1891",
            linhas=(LinhaRec(1, 0, 0, 100, 20, "linha manuscrita 1891", 0.85),),
            confianca_media=0.85,
            motor="tesseract",
        )

    monkeypatch.setattr(TesseractEngine, "available", fake_available)
    monkeypatch.setattr(TesseractEngine, "recognize_page", fake_recognize)

    entrada = tmp_path / "entrada"
    saida = tmp_path / "saida"
    entrada.mkdir()
    saida.mkdir()
    img = Image.new("RGB", (400, 100), color="white")
    img.save(entrada / "carta.png")

    cfg = AppConfig(entrada=entrada, saida=saida, banco=tmp_path / "banco.sqlite3", perfil="manuscrito")
    cfg.reconhecimento.engine = "kraken"
    # grava config para pipeline? pipeline usa cfg direto
    res_ing = ingerir_entrada(entrada, cfg, perfil="manuscrito")
    assert res_ing.novos == 1
    resumo = processar_documentos(cfg, engine_nome="kraken")
    assert resumo.paginas_ok == 1
    # verifica que PAGE-XML foi gerado
    base = "carta"
    assert (saida / base / f"{base}_page.xml").is_file()
    # verifica que kraken fallback não quebrou lote
