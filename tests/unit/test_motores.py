"""Testes do Marco 2: motores, TSV, fábrica e regra diplomática."""

from __future__ import annotations

import fitz
import pytest

from ocr_historico.pipeline import para_diplomatico
from ocr_historico.reconhecimento.base import (
    LinhaRec,
    MotorIndisponivel,
    RecognitionConfig,
    ResultadoPagina,
)
from ocr_historico.reconhecimento.ensemble import EnsembleEngine
from ocr_historico.reconhecimento.factory import criar_engine, motores_conhecidos
from ocr_historico.reconhecimento.kraken_engine import KrakenEngine
from ocr_historico.reconhecimento.pdf_text_engine import PdfTextEngine
from ocr_historico.reconhecimento.tesseract_engine import TesseractEngine

TSV_FIXTURE = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "1\t1\t0\t0\t0\t0\t0\t0\t800\t600\t-1\t\n"
    "5\t1\t1\t1\t1\t7\t60\t60\t400\t40\t88\tPresidente\n"
    "5\t1\t1\t1\t2\t13\t60\t120\t400\t40\t72\t1891\n"
    "5\t1\t1\t1\t3\t19\t60\t180\t100\t40\t-1\t\n"
)


class MotorFalso:
    name = "falso"

    def __init__(self, texto: str) -> None:
        self._texto = texto

    def available(self) -> bool:
        return True

    def recognize_page(self, image_path, config, numero_pagina: int = 1) -> ResultadoPagina:
        return ResultadoPagina(
            texto_bruto=self._texto,
            linhas=(LinhaRec(1, 0, 0, 10, 10, self._texto, 0.9),),
            confianca_media=0.9,
            motor=self.name,
        )


class TestTesseract:
    def test_parse_tsv_e_media(self, monkeypatch) -> None:
        class Proc:
            returncode = 0
            stdout = TSV_FIXTURE
            stderr = ""

        monkeypatch.setattr(TesseractEngine, "available", lambda self: True)
        monkeypatch.setattr("ocr_historico.reconhecimento.tesseract_engine.subprocess.run", lambda *a, **k: Proc())
        resultado = TesseractEngine().recognize_page("p.png", RecognitionConfig())
        assert [item.texto for item in resultado.linhas] == ["Presidente", "1891"]
        assert resultado.linhas[0].x == 60
        assert resultado.confianca_media == pytest.approx(0.80)
        assert resultado.texto_bruto == "Presidente\n1891"

    def test_ausente_da_mensagem_acionavel(self, monkeypatch) -> None:
        monkeypatch.setattr("ocr_historico.reconhecimento.tesseract_engine.shutil.which", lambda _: None)
        motor = TesseractEngine()
        assert motor.available() is False
        with pytest.raises(MotorIndisponivel, match="apt install"):
            motor.recognize_page("p.png", RecognitionConfig())


class TestOutrosMotores:
    def test_kraken_degrada_sem_quebrar(self, monkeypatch) -> None:
        import ocr_historico.reconhecimento.kraken_engine as km

        # O teste de fallback não deve depender do modelo instalado no workspace.
        monkeypatch.setattr(km, "_modelos_htr", lambda: [])
        motor = KrakenEngine()
        # sem modelo HTR local (blla é só segmentação), o motor segue indisponível p/ reconhecer
        assert motor.available() is False
        with pytest.raises(MotorIndisponivel, match="manuscrito|modelo HTR"):
            motor.recognize_page("p.png", RecognitionConfig())

    def test_pdf_texto_preserva_pagina(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "doc.pdf"
        with fitz.open() as doc:
            for texto in ("Primeira página 1891", "Segunda página 1907"):
                pagina = doc.new_page()
                pagina.insert_text((72, 72), texto)
            doc.save(alvo)
        motor = PdfTextEngine()
        primeira = motor.recognize_page(alvo, RecognitionConfig(), numero_pagina=1)
        assert "1891" in primeira.texto_bruto
        assert "1907" not in primeira.texto_bruto
        segunda = motor.recognize_page(alvo, RecognitionConfig(), numero_pagina=2)
        assert "1907" in segunda.texto_bruto

    def test_fabrica_desconhecido_erro_claro(self) -> None:
        with pytest.raises(ValueError, match="Motor desconhecido"):
            criar_engine("inexistente")
        assert {"tesseract", "kraken", "pdf_texto", "ensemble"} <= set(motores_conhecidos())

    def test_ensemble_nao_inventa_texto(self) -> None:
        primario = MotorFalso("texto primário")
        igual = MotorFalso("texto primário")
        diferente = MotorFalso("outro texto")
        sem_div = EnsembleEngine([primario, igual]).recognize_page("x", RecognitionConfig())
        assert sem_div.texto_bruto == "texto primário"
        assert sem_div.divergencias == ()
        com_div = EnsembleEngine([primario, diferente]).recognize_page("x", RecognitionConfig())
        assert com_div.texto_bruto == "texto primário"
        assert len(com_div.divergencias) == 1


class TestDiplomatico:
    def test_colapsa_espacos_sem_modernizar(self) -> None:
        bruto = "Illm.  Snr.   Presldente  \nrecebí   a  carta de 1891."
        assert para_diplomatico(bruto) == "Illm. Snr. Presldente\nrecebí a carta de 1891."
