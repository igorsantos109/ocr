"""Integração do Marco 2: pipeline com motor simulado, retomada e exportação."""

from __future__ import annotations

import json

import fitz
from PIL import Image
from sqlalchemy import func, select
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.config import carregar_config
from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.ingestao import ingerir_entrada
from ocr_historico.models import Documento, Linha
from ocr_historico.pipeline import exportar_documento, processar_documentos
from ocr_historico.reconhecimento.base import LinhaRec, ResultadoPagina

runner = CliRunner()


class MotorSimulado:
    name = "simulado"

    def available(self) -> bool:
        return True

    def recognize_page(self, image_path, config, numero_pagina: int = 1) -> ResultadoPagina:
        texto = f"Acta  da  sessão {numero_pagina} de 1891"
        return ResultadoPagina(
            texto_bruto=texto,
            linhas=(LinhaRec(numero_pagina, 10, 20, 100, 30, texto, 0.85),),
            confianca_media=0.85,
            motor=self.name,
        )


def _preparar(diretorio_tmp):
    entrada = diretorio_tmp / "entrada"
    entrada.mkdir()
    with fitz.open() as doc:
        for _ in range(2):
            pagina = doc.new_page()
            pagina.insert_text((72, 72), "Texto para OCR. " * 5)
        doc.save(entrada / "livro.pdf")
    Image.new("RGB", (1200, 1600), "white").save(entrada / "carta.png")
    base = diretorio_tmp / "config.yaml"
    base.write_text(
        f"perfil: impresso_historico\nrender_dpi: 150\n"
        f"saida: {diretorio_tmp / 'saida'}\nbanco: {diretorio_tmp / 'b.sqlite3'}\n",
        encoding="utf-8",
    )
    return entrada, str(base)


class TestPipeline:
    def test_ocr_exporta_e_retoma(self, diretorio_tmp, monkeypatch) -> None:
        entrada, cfg = _preparar(diretorio_tmp)
        monkeypatch.setattr("ocr_historico.pipeline.criar_engine", lambda nome: MotorSimulado())
        dados = carregar_config(cfg)
        resumo_ing = ingerir_entrada(entrada, dados)
        assert resumo_ing.novos == 2

        resumo = processar_documentos(dados)
        assert resumo.documentos == 2
        assert resumo.paginas_ok == 3
        assert resumo.paginas_erro == 0

        engine = inicializar_banco(diretorio_tmp / "b.sqlite3")
        with fabrica_sessoes(engine)() as sessao:
            assert sessao.scalar(select(func.count(Linha.id))) == 3
            linha = sessao.scalars(select(Linha)).first()
            assert linha.texto_bruto == "Acta  da  sessão 1 de 1891"
            assert linha.texto_diplomatico == "Acta da sessão 1 de 1891"
            assert linha.confianca == 0.85
            assert linha.exige_revisao is False
            assert linha.status_revisao == "baixa"
            docs = sessao.scalars(select(Documento)).all()
            assert {d.status for d in docs} == {"concluido"}

        saida = diretorio_tmp / "saida"
        for nome in ("livro", "carta"):
            pasta = saida / nome
            assert (pasta / f"{nome}_bruto.txt").is_file()
            assert (pasta / f"{nome}_diplomatico.txt").is_file()
            assert (pasta / f"{nome}.md").is_file()
            assert (pasta / f"{nome}.tsv").is_file()
            assert (pasta / f"{nome}.hocr").is_file()
            assert (pasta / f"{nome}_page.xml").is_file()
            assert (pasta / f"{nome}_relatorio.html").is_file()
            assert (pasta / "baixa_confianca.csv").is_file()
            assert (pasta / "overlays").is_dir()
            carga = json.loads((pasta / f"{nome}.json").read_text(encoding="utf-8"))
            assert carga["schema_version"] == "1.0"
            assert carga["documento"]["sha256"]
            assert carga["execucao"]["motores"]
            assert carga["paginas"][0]["linhas"][0]["x"] == 10
            assert carga["paginas"][0]["linhas"][0]["prioridade"] in {"alta", "média", "baixa"}

        segunda = processar_documentos(dados)
        assert segunda.paginas_ok == 0  # páginas concluídas são puladas
        with fabrica_sessoes(engine)() as sessao:
            assert sessao.scalar(select(func.count(Linha.id))) == 3

        with fabrica_sessoes(engine)() as sessao:
            alvo = sessao.scalars(select(Documento)).first()
            pasta = exportar_documento(dados, alvo.id)
            assert pasta.is_dir()
        resultado = runner.invoke(app, ["exportar", alvo.id, "--config", cfg])
        assert resultado.exit_code == 0, resultado.output
        assert "Exportado em" in resultado.output
        faltando = runner.invoke(app, ["exportar", "inexistente", "--config", cfg])
        assert faltando.exit_code == 2
