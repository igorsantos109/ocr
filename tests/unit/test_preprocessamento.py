"""Testes do Marco 2: pré-processamento puro e por perfil."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from ocr_historico.qualidade.preprocessamento import (
    ampliar,
    aplicar_pipeline,
    binarizar,
    corrigir_inclinacao,
    ler_cinza,
    para_cinza,
    realce_clahe,
    reduzir_ruido,
    tem_opencv,
)

pytestmark = pytest.mark.skipif(not tem_opencv(), reason="OpenCV ausente neste host")


def _imagem_texto(caminho, linhas: int = 3):
    img = Image.new("RGB", (800, 600), "white")
    desenho = ImageDraw.Draw(img)
    for i in range(linhas):
        desenho.text((60, 60 + i * 120), "Carta de 1891 ao presidente", fill="black")
    img.save(caminho)
    return caminho


class TestFuncoes:
    def test_cinza_tem_2_dimensoes(self, diretorio_tmp) -> None:
        alvo = _imagem_texto(diretorio_tmp / "a.png")
        cinza = para_cinza(ler_cinza(alvo))
        assert cinza.ndim == 2
        assert cinza.shape == (600, 800)

    def test_deskew_em_branco_e_angulo_zero(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "branco.png"
        Image.new("RGB", (400, 300), "white").save(alvo)
        _, angulo = corrigir_inclinacao(ler_cinza(alvo))
        assert angulo == 0.0

    def test_clahe_e_denoise_mantem_dimensoes(self, diretorio_tmp) -> None:
        alvo = _imagem_texto(diretorio_tmp / "b.png")
        cinza = ler_cinza(alvo)
        assert realce_clahe(cinza).shape == cinza.shape
        assert reduzir_ruido(cinza, "leve").shape == cinza.shape

    def test_upscale_e_binarizacao(self, diretorio_tmp) -> None:
        alvo = _imagem_texto(diretorio_tmp / "c.png")
        cinza = ler_cinza(alvo)
        assert ampliar(cinza, 1.5).shape == (900, 1200)
        assert set(__import__("numpy").unique(binarizar(cinza)).tolist()) <= {0, 255}

    def test_pipeline_do_perfil_salva_derivada(self, diretorio_tmp) -> None:
        alvo = _imagem_texto(diretorio_tmp / "d.png")
        destino = diretorio_tmp / "pre" / "p0001.png"
        pre = SimpleNamespace(
            denoise="leve",
            deskew=True,
            clahe=True,
            remover_fundo=True,
            upscale=1.0,
            binarizacao=False,
        )
        meta = aplicar_pipeline(alvo, destino, pre)
        assert destino.is_file()
        assert "deskew" in meta["etapas"]
        assert "clahe" in meta["etapas"]
        assert alvo.stat().st_size > 0
