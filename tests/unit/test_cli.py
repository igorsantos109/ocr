"""Testes do Marco 0: CLI, setup e diagnosticar."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ocr_historico.cli import app

runner = CliRunner()


def ejecutar(*args: str):
    return runner.invoke(app, list(args))


def _config_tmp(diretorio_tmp: Path, nombre: str = "config.yaml") -> Path:
    ruta = diretorio_tmp / nombre
    if not ruta.exists():
        ruta.write_text("perfil: automatico\n", encoding="utf-8")
    return ruta


class TestAyuda:
    def test_version(self) -> None:
        resultado = ejecutar("--version")
        assert resultado.exit_code == 0
        assert "0.4.0" in resultado.stdout

    def test_help_raiz_enumera_comandos(self) -> None:
        resultado = ejecutar("--help")
        assert resultado.exit_code == 0
        assert "setup" in resultado.stdout
        assert "diagnosticar" in resultado.stdout

    def test_help_em_portugues(self) -> None:
        resultado = ejecutar("--help")
        assert resultado.exit_code == 0
        assert "documentos históricos brasileiros" in resultado.stdout


class TestSetup:
    def test_inicializa_banco_por_defecto(self, raiz_projeto: Path) -> None:
        resultado = ejecutar("setup", "--config", str(raiz_projeto / "configs" / "default.yaml"))
        assert resultado.exit_code == 0
        assert "Banco SQLite inicializado" in resultado.stdout
        assert (raiz_projeto / "data" / "ocr_historico.sqlite3").is_file()

    def test_config_inexistente_falla_limpio(self, diretorio_tmp: Path) -> None:
        resultado = ejecutar("setup", "--config", str(diretorio_tmp / "nope.yaml"))
        assert resultado.exit_code != 0

    def test_cria_diretorios_so_com_confirmacao(self, diretorio_tmp: Path) -> None:
        cfg = _config_tmp(diretorio_tmp)
        entrada = diretorio_tmp / "entrada_ausente"
        salida = diretorio_tmp / "salida_ausente"
        cfg.write_text(
            f"perfil: automatico\nentrada: {entrada}\nsaida: {salida}\nbanco: {diretorio_tmp / 'b.sqlite3'}\n",
            encoding="utf-8",
        )
        resultado = ejecutar("setup", "--config", str(cfg), "--criar-diretorios", "--sim")
        assert resultado.exit_code == 0, resultado.output
        assert entrada.is_dir()
        assert salida.is_dir()

    def test_setup_es_idempotente(self, diretorio_tmp: Path) -> None:
        cfg = _config_tmp(diretorio_tmp)
        cfg.write_text(f"perfil: automatico\nbanco: {diretorio_tmp / 'b.sqlite3'}\n", encoding="utf-8")
        primero = ejecutar("setup", "--config", str(cfg))
        segundo = ejecutar("setup", "--config", str(cfg))
        assert primero.exit_code == 0
        assert segundo.exit_code == 0


class TestDiagnostico:
    def test_funciona_sin_dependencias_opcionales(self, raiz_projeto: Path) -> None:
        resultado = ejecutar("diagnosticar", "--config", str(raiz_projeto / "configs" / "default.yaml"))
        assert resultado.exit_code == 0
        assert "Python" in resultado.stdout
        assert "Banco SQLite" in resultado.stdout
        assert "Tesseract" in resultado.stdout

    def test_config_invalida_da_erro_nao_fatal(self, diretorio_tmp: Path) -> None:
        ruta = diretorio_tmp / "malo.yaml"
        ruta.write_text("confianca:\n  limiar_alta: 0.82\n  limiar_revisao: 0.70\n", encoding="utf-8")
        resultado = ejecutar("diagnosticar", "--config", str(ruta))
        assert resultado.exit_code == 2
        assert "ERRO de configuração" in (resultado.stdout or resultado.stderr)
