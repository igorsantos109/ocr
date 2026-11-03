"""Testes para carregamento de configuração padrão e caminhos de entrada."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ocr_historico.config import (
    caminho_config_padrao,
    carregar_config,
    config_padrao_embutida,
)


class TestConfigPadraoInstalacao:
    """O CLI deve encontrar a configuração padrão em código-fonte, -e e wheel."""

    def test_caminho_padrao_encontra_arquivo_repo(self, raiz_projeto: Path) -> None:
        """Execução a partir do código-fonte encontra configs/default.yaml."""
        esperado = raiz_projeto / "configs" / "default.yaml"
        resultado = caminho_config_padrao()
        assert resultado.is_file()
        assert resultado == esperado or resultado.name == "default.yaml"

    def test_configuracao_embutida_valida(self) -> None:
        """AppConfig() padrão não falha mesmo sem arquivo de configuração."""
        cfg = config_padrao_embutida()
        assert cfg.perfil == "automatico"
        assert cfg.reconhecimento.engine == "tesseract"
        assert cfg.reconhecimento.timeout_segundos == 300

    def test_timeout_zerou_nao_valido(self, diretorio_tmp: Path) -> None:
        """timeout_segundos <= 0 deve ser rejeitado pelo Pydantic."""
        ruta = diretorio_tmp / "malo.yaml"
        ruta.write_text("reconhecimento:\n  timeout_segundos: 0\n", encoding="utf-8")
        with pytest.raises(ValidationError):
            carregar_config(ruta)

    def test_timeout_negativo_nao_valido(self, diretorio_tmp: Path) -> None:
        ruta = diretorio_tmp / "malo2.yaml"
        ruta.write_text("reconhecimento:\n  timeout_segundos: -5\n", encoding="utf-8")
        with pytest.raises(ValidationError):
            carregar_config(ruta)

    def test_timeout_valido_aceito(self, diretorio_tmp: Path) -> None:
        ruta = diretorio_tmp + "/bom.yaml" if False else diretorio_tmp / "bom.yaml"
        ruta.write_text("reconhecimento:\n  timeout_segundos: 120\n", encoding="utf-8")
        cfg = carregar_config(ruta)
        assert cfg.reconhecimento.timeout_segundos == 120

    def test_variavel_ambiente_com_default(self, diretorio_tmp: Path, monkeypatch) -> None:
        """${VAR:default} usa o default quando a variável não está definida."""
        monkeypatch.delenv("OCRHIST_ENTRADA", raising=False)
        ruta = diretorio_tmp / "env.yaml"
        ruta.write_text(
            "entrada: ${OCRHIST_ENTRADA:~/Área de trabalho/OCRENTRADA}\n"
            "saida: ${OCRHIST_SAIDA:~/Área de trabalho/OCRSAIDA}\n",
            encoding="utf-8",
        )
        cfg = carregar_config(ruta)
        assert str(cfg.entrada).endswith("Área de trabalho/OCRENTRADA")
        assert str(cfg.saida).endswith("Área de trabalho/OCRSAIDA")

    def test_variavel_ambiente_override(self, diretorio_tmp: Path, monkeypatch) -> None:
        """${VAR:default} usa o valor da variável quando definida."""
        monkeypatch.setenv("OCRHIST_ENTRADA", "/tmp/minha-entrada")
        ruta = diretorio_tmp / "env2.yaml"
        ruta.write_text(
            "entrada: ${OCRHIST_ENTRADA:~/Área de trabalho/OCRENTRADA}\n",
            encoding="utf-8",
        )
        cfg = carregar_config(ruta)
        assert str(cfg.entrada) == "/tmp/minha-entrada"

    def test_expande_tilde_no_caminho(self, diretorio_tmp: Path) -> None:
        """Caminhos com ~ devem ser expandidos para o home do usuário."""
        ruta = diretorio_tmp / "tilde.yaml"
        ruta.write_text("entrada: ~/Área de trabalho/OCRENTRADA\n", encoding="utf-8")
        cfg = carregar_config(ruta)
        assert str(cfg.entrada).startswith(str(Path.home()))
