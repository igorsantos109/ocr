"""Integração do Marco 1: lote PDF+PNG+TIFF, retomada e originais intactos."""

from __future__ import annotations

import fitz
from PIL import Image
from sqlalchemy import func, select
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.ingestao.hash import calcular_sha256
from ocr_historico.models import Documento, Pagina

runner = CliRunner()


def _lote(entrada) -> None:
    with fitz.open() as doc:
        for _ in range(2):
            pagina = doc.new_page()
            pagina.insert_text((72, 72), "Jornal de 1907. " * 10)
        doc.save(entrada / "jornal_1907.pdf")
    Image.new("RGB", (1200, 1600), "white").save(entrada / "carta.PNG")
    quadros = [Image.new("RGB", (1200, 1600), "white") for _ in range(2)]
    quadros[0].save(entrada / "fotos.tif", save_all=True, append_images=quadros[1:])
    (entrada / ".oculto.png").write_bytes(b"x")
    (entrada / "notas.txt").write_text("fora do escopo", encoding="utf-8")


def _config(diretorio_tmp, entrada) -> str:
    cfg = diretorio_tmp / "config.yaml"
    cfg.write_text(
        f"perfil: automatico\nrender_dpi: 150\nentrada: {entrada}\n"
        f"saida: {diretorio_tmp / 'saida'}\nbanco: {diretorio_tmp / 'b.sqlite3'}\n",
        encoding="utf-8",
    )
    return str(cfg)


class TestLote:
    def test_processa_pula_e_forca(self, diretorio_tmp) -> None:
        entrada = diretorio_tmp / "entrada"
        entrada.mkdir()
        _lote(entrada)
        cfg = _config(diretorio_tmp, entrada)

        primeira = runner.invoke(app, ["processar", str(entrada), "--config", cfg, "--somente-ingestao"])
        assert primeira.exit_code == 0, primeira.output
        assert "3 novo(s)" in primeira.output

        engine = inicializar_banco(diretorio_tmp / "b.sqlite3")
        with fabrica_sessoes(engine)() as sessao:
            assert sessao.scalar(select(func.count(Documento.id))) == 3
            assert sessao.scalar(select(func.count(Pagina.id))) == 5
            pdf = sessao.scalar(select(Documento).where(Documento.tipo_arquivo == "pdf"))
            assert pdf.numero_paginas == 2
            assert pdf.configuracao_json["camada_textual"] is True

        segunda = runner.invoke(app, ["processar", str(entrada), "--config", cfg, "--somente-ingestao"])
        assert segunda.exit_code == 0
        assert "3 pulado(s)" in segunda.output

        forcada = runner.invoke(app, ["processar", str(entrada), "--config", cfg, "--forcar", "--somente-ingestao"])
        assert forcada.exit_code == 0
        assert "3 novo(s)" in forcada.output
        with fabrica_sessoes(engine)() as sessao:
            assert sessao.scalar(select(func.count(Documento.id))) == 3
            assert sessao.scalar(select(func.count(Pagina.id))) == 5

    def test_falha_isolada_e_originais_intactos(self, diretorio_tmp) -> None:
        entrada = diretorio_tmp / "entrada"
        entrada.mkdir()
        _lote(entrada)
        (entrada / "quebrado.pdf").write_bytes(b"isto nao e um pdf valido")
        cfg = _config(diretorio_tmp, entrada)
        hashes_antes = {p.name: calcular_sha256(p) for p in entrada.iterdir() if p.is_file()}

        resultado = runner.invoke(app, ["processar", str(entrada), "--config", cfg, "--somente-ingestao"])
        assert resultado.exit_code == 1
        assert "1 erro(s)" in resultado.output
        assert {p.name: calcular_sha256(p) for p in entrada.iterdir() if p.is_file()} == hashes_antes

        engine = inicializar_banco(diretorio_tmp / "b.sqlite3")
        with fabrica_sessoes(engine)() as sessao:
            falhou = sessao.scalars(select(Documento).where(Documento.status == "erro")).all()
            assert len(falhou) == 1
            prontos = sessao.scalars(select(Documento).where(Documento.status == "aguardando_ocr")).all()
            assert len(prontos) == 3

        so_falhas = runner.invoke(
            app, ["processar", str(entrada), "--config", cfg, "--retry-failed", "--somente-ingestao"]
        )
        assert so_falhas.exit_code == 1
        listado = runner.invoke(app, ["listar", "--config", cfg])
        assert listado.exit_code == 0
        assert "jornal_1907.pdf" in listado.output
        estado = runner.invoke(app, ["status", "--config", cfg])
        assert estado.exit_code == 0
        assert "aguardando_ocr: 3" in estado.output
