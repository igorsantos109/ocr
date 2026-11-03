"""Testes de validação de caminhos de entrada no CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ocr_historico.cli import app

runner = CliRunner()


def test_inventariar_caminho_inexistente_erro_limpo() -> None:
    """Caminho não existente deve gerar mensagem clara, sem stack trace."""
    resultado = runner.invoke(app, ["inventariar", "/caminho/que/nao/existe"])
    assert resultado.exit_code != 0
    assert "não encontrado" in (resultado.stdout + resultado.stderr)
    assert "Traceback" not in (resultado.stdout + resultado.stderr)


def test_inventariar_arquivo_valido(diretorio_tmp: Path) -> None:
    """Arquivo existente deve ser aceito (não lança erro de caminho)."""
    arquivo = diretorio_tmp / "documento.pdf"
    arquivo.write_bytes(b"%PDF-1.4 fake")
    resultado = runner.invoke(app, ["inventariar", str(arquivo)])
    # Pode falhar por falta de banco/etc., mas não por caminho inválido
    saida = resultado.stdout + resultado.stderr
    assert "Caminho de entrada não encontrado" not in saida


def test_inventariar_diretorio_vazio(diretorio_tmp: Path) -> None:
    """Diretório existente (vazio) deve ser aceito."""
    pasta = diretorio_tmp / "minha_pasta"
    pasta.mkdir()
    resultado = runner.invoke(app, ["inventariar", str(pasta)])
    saida = resultado.stdout + resultado.stderr
    assert "Caminho de entrada não encontrado" not in saida


def test_processar_caminho_inexistente_erro_limpo() -> None:
    resultado = runner.invoke(app, ["processar", "/caminho/que/nao/existe"])
    assert resultado.exit_code != 0
    saida = resultado.stdout + resultado.stderr
    assert "não encontrado" in saida
    assert "Traceback" not in saida
