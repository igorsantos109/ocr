"""Integração do comando avaliar via CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from ocr_historico.cli import app

runner = CliRunner()


def _escrever(diretorio, nome: str, conteudo: str):
    caminho = diretorio / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return str(caminho)


class TestAvaliar:
    def test_cer_wer_zero_para_textos_iguais(self, diretorio_tmp) -> None:
        ref = _escrever(diretorio_tmp, "ref.txt", "Presidente do Brasil 1891")
        hip = _escrever(diretorio_tmp, "hip.txt", "Presidente do Brasil 1891")
        resultado = runner.invoke(app, ["avaliar", "--referencia", ref, "--hipotese", hip])
        assert resultado.exit_code == 0, resultado.output
        assert "CER: 0.0000" in resultado.output
        assert "WER: 0.0000" in resultado.output
        assert "não são acurácia" in resultado.output

    def test_relatorio_json_e_erros(self, diretorio_tmp) -> None:
        ref = _escrever(diretorio_tmp, "ref.txt", "uma duas tres")
        hip = _escrever(diretorio_tmp, "hip.txt", "uma duas")
        rel = diretorio_tmp / "relatorio.json"
        resultado = runner.invoke(
            app,
            [
                "avaliar",
                "--referencia",
                ref,
                "--hipotese",
                hip,
                "--relatorio",
                str(rel),
            ],
        )
        assert resultado.exit_code == 0, resultado.output
        carga = json.loads(rel.read_text(encoding="utf-8"))
        assert carga["wer"]["distancia"] == 1
        ausente = runner.invoke(app, ["avaliar", "--referencia", "nope", "--hipotese", hip])
        assert ausente.exit_code == 2
