"""Testes do Marco 0: configuração YAML validada."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ocr_historico.config import AppConfig, carregar_config, config_padrao_embutida

RAIZ = Path(__file__).resolve().parents[2]


class TestCargarConfig:
    def test_carga_valida_yaml_del_repo(self, raiz_projeto: Path) -> None:
        cfg = carregar_config(raiz_projeto / "configs" / "default.yaml")
        assert isinstance(cfg, AppConfig)
        assert cfg.perfil == "automatico"
        assert cfg.reconhecimento.engine == "tesseract"
        assert cfg.confianca.limiar_revisao == 0.82

    def test_perfil_manuscrito_no_binariza_por_defecto(self, raiz_projeto: Path) -> None:
        cfg = carregar_config(raiz_projeto / "configs" / "manuscrito.yaml")
        assert cfg.preprocessamento.binarizacao is False
        assert cfg.reconhecimento.engine == "kraken"

    def test_arquivo_inexistente_lanca(self, diretorio_tmp: Path) -> None:
        with pytest.raises(FileNotFoundError):
            carregar_config(diretorio_tmp / "no_existe.yaml")

    def test_yaml_invalido_lanza(self, diretorio_tmp: Path) -> None:
        ruta = diretorio_tmp / "roto.yaml"
        ruta.write_text("perfil: [no:es:una:lista\n", encoding="utf-8")
        with pytest.raises((ValueError, ValidationError)):
            carregar_config(ruta)

    def test_limiar_incoherente_lanza(self, diretorio_tmp: Path) -> None:
        ruta = diretorio_tmp / "malo.yaml"
        ruta.write_text("confianca:\n  limiar_alta: 0.82\n  limiar_revisao: 0.70\n", encoding="utf-8")
        with pytest.raises(ValidationError):
            carregar_config(ruta)

    def test_padrao_tem_rotas_configuraveis(self) -> None:
        cfg = config_padrao_embutida()
        assert cfg.entrada.name == "OCRENTRADA"
        assert cfg.saida.name == "OCRSAIDA"
        assert cfg.llm.enabled is False
