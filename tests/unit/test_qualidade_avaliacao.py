"""Testes do Marco 3: CER/WER e classificação de confiança."""

from __future__ import annotations

import pytest

from ocr_historico.avaliacao import calcular_cer, calcular_wer
from ocr_historico.posprocessamento.confianca import calcular_confianca, classificar_revisao


class TestCer:
    def test_textos_iguais_cer_zero(self) -> None:
        resultado = calcular_cer("Presidente do Brasil", "Presidente do Brasil")
        assert resultado.valor == 0.0
        assert resultado.distancia == 0

    def test_cer_um_caractere(self) -> None:
        resultado = calcular_cer("abc", "abd")
        assert resultado.distancia == 1
        assert resultado.substituicoes == 1
        assert resultado.valor == pytest.approx(1 / 3)

    def test_insercoes_e_delecoes(self) -> None:
        ins = calcular_cer("abc", "abcd")
        dele = calcular_cer("abcd", "abc")
        assert ins.insercoes == 1
        assert dele.delecoes == 1
        assert ins.valor == pytest.approx(1 / 3)
        assert dele.valor == pytest.approx(1 / 4)

    def test_referencia_vazia(self) -> None:
        assert calcular_cer("", "").valor == 0.0
        assert calcular_cer("", "x").valor == 1.0

    def test_normalizacao_opcional(self) -> None:
        bruta = calcular_cer("Carta  de  1891", "carta de 1891", normalizar=True)
        assert bruta.valor == 0.0


class TestWer:
    def test_uma_palavra_errada(self) -> None:
        resultado = calcular_wer("presidente do brasil", "presidente da brasil")
        assert resultado.distancia == 1
        assert resultado.valor == pytest.approx(1 / 3)

    def test_tokens_iguais(self) -> None:
        assert calcular_wer("um dois três", "um dois três").valor == 0.0

    def test_contagem_de_operacoes(self) -> None:
        resultado = calcular_wer("a b c", "a b c d")
        assert resultado.insercoes == 1
        assert resultado.referencia == 3


class TestConfianca:
    def test_motor_ausente_vai_para_revisao(self) -> None:
        avaliacao = classificar_revisao(None)
        assert avaliacao.prioridade == "alta"
        assert avaliacao.exige_revisao is True

    def test_limiares(self) -> None:
        assert classificar_revisao(0.50).prioridade == "alta"
        assert classificar_revisao(0.75).prioridade == "média"
        assert classificar_revisao(0.90).prioridade == "baixa"

    def test_sinais_reduzem_confianca(self) -> None:
        base = calcular_confianca(0.90, texto="Presidente 1891")
        assert calcular_confianca(0.90, nitidez=5, texto="Presidente 1891") < base
        assert calcular_confianca(0.90, texto="Presidente 18@@91") < base
        assert calcular_confianca(0.90, divergente=True) < base

    def test_valores_fora_do_intervalo_sao_limites(self) -> None:
        assert 0.0 <= calcular_confianca(-2.0) <= 1.0
        assert 0.0 <= calcular_confianca(3.0) <= 1.0

    def test_sem_motor_permanece_none(self) -> None:
        assert calcular_confianca(None) is None
