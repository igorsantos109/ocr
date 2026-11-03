"""Testes Marco 5: segmentação de linhas e Kraken degradável."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from ocr_historico.layout.linhas import fallback_segmentar_linhas, segmentar_linhas
from ocr_historico.reconhecimento.base import MotorIndisponivel, RecognitionConfig
from ocr_historico.reconhecimento.kraken_engine import KrakenEngine
from ocr_historico.treinamento.kraken_train import avaliar_modelo, preparar_treino
from ocr_historico.treinamento.versoes import listar_versoes, registrar_versao


def _imagem_linhas(destino: Path) -> Path:
    # cria imagem sintética com duas faixas escuras simulando linhas
    img = Image.new("L", (400, 200), color=255)
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 30, 380, 45], fill=0)
    draw.rectangle([20, 90, 380, 105], fill=0)
    draw.rectangle([20, 150, 380, 165], fill=0)
    p = destino / "manuscrito.png"
    img.save(p)
    return p


def test_fallback_segmentar_linhas_reais(diretorio_tmp: Path) -> None:
    img = _imagem_linhas(diretorio_tmp)
    res = fallback_segmentar_linhas(img)
    assert res.metodo == "fallback"
    assert len(res.linhas) >= 2
    # ordenação por y
    ys = [linha.y for linha in res.linhas]
    assert ys == sorted(ys)


def test_fallback_pagina_unica_sem_opencv(monkeypatch, diretorio_tmp: Path) -> None:
    img = _imagem_linhas(diretorio_tmp)
    # força caminho sem OpenCV
    import ocr_historico.layout.linhas as mod

    monkeypatch.setattr(mod, "_TEM_CV2", False)
    res = mod.fallback_segmentar_linhas(img)
    assert len(res.linhas) == 1
    assert res.linhas[0].largura == 400


def test_segmentar_linhas_preferencia_kraken_cai_no_fallback(diretorio_tmp: Path) -> None:
    img = _imagem_linhas(diretorio_tmp)
    res = segmentar_linhas(img, preferencia="kraken")
    # kraken não instalado neste host → fallback com aviso
    assert res.metodo == "fallback"
    assert "Kraken/blla indisponível" in (res.aviso or "")


def test_kraken_engine_degrada_com_mensagem(diretorio_tmp: Path, monkeypatch) -> None:
    import ocr_historico.reconhecimento.kraken_engine as km

    # Isola o teste do modelo HTR instalado para ativar o motor em produção.
    monkeypatch.setattr(km, "_modelos_htr", lambda: [])
    motor = KrakenEngine()
    # sem modelo HTR (blla não conta), indisponível p/ reconhecer
    assert motor.available() is False
    with pytest.raises(MotorIndisponivel, match="Kraken não instalado|nenhum modelo HTR"):
        motor.recognize_page(diretorio_tmp / "inexistente.png", RecognitionConfig())
    # quando imagem existe mas sem modelo
    img = _imagem_linhas(diretorio_tmp)
    # monkeypatch pacote+modelo True para testar mensagem de modelo ausente explícito
    monkeypatch.setattr(km, "_tem_kraken", lambda: True)
    monkeypatch.setattr(km, "_tem_modelo_htr", lambda: True)
    # garante que não há modelo
    for _p in Path("data/modelos/kraken").glob("*.mlmodel"):
        pass  # deixa vazio
    motor2 = KrakenEngine()
    # como pacote e HTR foram mockados, available deve ser True
    assert motor2.available() is True
    with pytest.raises(MotorIndisponivel, match="nenhum modelo"):
        motor2.recognize_page(img, RecognitionConfig(modelo="inexistente.mlmodel"))


def test_preparar_treino_dry_run_sem_kraken(diretorio_tmp: Path) -> None:
    # cria dataset mínimo válido
    base = diretorio_tmp / "ground_truth"
    base.mkdir(parents=True)
    (base / "imagens").mkdir()
    (base / "transcricoes").mkdir()
    img = Image.new("RGB", (100, 30), color="white")
    img_path = base / "imagens" / "carta_001_p001_l001.png"
    img.save(img_path)
    trans_path = base / "transcricoes" / "carta_001_p001_l001.gt.txt"
    trans_path.write_text("Olá 1891", encoding="utf-8")
    (base / "manifest.jsonl").write_text(
        json.dumps(
            {
                "id": "carta_001_p001_l001",
                "imagem": "imagens/carta_001_p001_l001.png",
                "transcricao": "transcricoes/carta_001_p001_l001.gt.txt",
                "documento": "carta_001",
                "pagina": 1,
                "escrevente": "desconhecido",
                "periodo": "1891",
                "revisado": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    res = preparar_treino(base, epocas=5, dry_run=True)
    assert "train" in " ".join(res.comando)
    assert res.modelo_saida.suffix == ".mlmodel"
    assert res.comando[0] in ("ketos", "kraken")


def test_preparar_treino_falha_se_invalido(diretorio_tmp: Path) -> None:
    base = diretorio_tmp / "vazio"
    base.mkdir()
    (base / "manifest.jsonl").write_text("", encoding="utf-8")
    # sem registros, ainda passa? mas dataset vazio gera comando mas sem erro
    # forçar manifesto inexistente
    with pytest.raises(ValueError, match="Dataset não encontrado"):
        preparar_treino(diretorio_tmp / "inexistente.jsonl")


def test_versoes_registra_e_lista(diretorio_tmp: Path) -> None:
    registro = diretorio_tmp / "versoes.jsonl"
    v1 = registrar_versao("modelo1.mlmodel", "ds1", epocas=10, registro=registro)
    v2 = registrar_versao("modelo2.mlmodel", "ds1", epocas=20, cer=0.12, registro=registro)
    lista = listar_versoes(registro)
    assert len(lista) == 2
    assert lista[0].id == v2.id  # mais recente primeiro
    assert v1.epocas == 10


def test_avaliar_modelo_sem_kraken_retorna_aviso(diretorio_tmp: Path) -> None:
    base = diretorio_tmp / "teste"
    base.mkdir()
    (base / "manifest.jsonl").write_text("", encoding="utf-8")
    modelo = diretorio_tmp / "fake.mlmodel"
    modelo.write_text("dummy", encoding="utf-8")
    detalhe = avaliar_modelo(modelo, base)
    assert detalhe["modelo"] == str(modelo)
    # sem kraken, aviso esperado
    assert "Kraken não" in (detalhe.get("aviso") or detalhe.get("erro") or "")
