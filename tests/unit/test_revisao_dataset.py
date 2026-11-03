"""Testes do Marco 4: correção auditável, fila ativa e dataset."""

from __future__ import annotations

import json

import pytest
from PIL import Image
from sqlalchemy import select

from ocr_historico.avaliacao.active_learning import selecionar_linhas
from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.models import Correcao, Documento, Linha, Pagina
from ocr_historico.revisao import corrigir_linha, listar_fila, marcar_linha
from ocr_historico.treinamento.dataset import (
    exportar_linhas_revisadas,
    iniciar_dataset,
    validar_dataset,
)
from ocr_historico.treinamento.split import dividir_manifesto


def _banco_com_linhas(diretorio_tmp):
    banco = diretorio_tmp / "b.sqlite3"
    engine = inicializar_banco(banco)
    imagem = diretorio_tmp / "linha.png"
    Image.new("RGB", (300, 80), "white").save(imagem)
    with fabrica_sessoes(engine)() as sessao:
        doc = Documento(
            id="doc-1",
            caminho_original="/orig/doc.pdf",
            nome_original="doc.pdf",
            sha256="d" * 64,
            tipo_arquivo="pdf",
            perfil="impresso_moderno",
            numero_paginas=1,
            status="concluido",
            configuracao_json={},
        )
        pagina = Pagina(
            id="pag-1",
            documento=doc,
            numero=1,
            imagem_original=str(imagem),
            imagem_pre_processada=str(imagem),
            largura=300,
            altura=80,
            status="concluida",
        )
        sessao.add(doc)
        sessao.flush()
        sessao.add_all(
            [
                Linha(
                    id="linha-baixa",
                    pagina=pagina,
                    numero=1,
                    x=1,
                    y=2,
                    largura=100,
                    altura=20,
                    texto_bruto="Illm. Snr.",
                    texto_diplomatico="Illm. Snr.",
                    confianca=0.4,
                    exige_revisao=True,
                    status_revisao="alta",
                    imagem_linha=str(imagem),
                ),
                Linha(
                    id="linha-alta",
                    pagina=pagina,
                    numero=2,
                    x=1,
                    y=30,
                    largura=100,
                    altura=20,
                    texto_bruto="Presidente",
                    texto_diplomatico="Presidente",
                    confianca=0.95,
                    exige_revisao=False,
                    status_revisao="baixa",
                    imagem_linha=str(imagem),
                ),
            ]
        )
        sessao.commit()
    return banco


class TestRevisao:
    def test_fila_prioriza_baixa_confianca(self, diretorio_tmp) -> None:
        banco = _banco_com_linhas(diretorio_tmp)
        fila = listar_fila(banco)
        assert [item.linha_id for item in fila] == ["linha-baixa"]
        assert fila[0].prioridade == "alta"

    def test_correcao_cria_trilha_e_fecha_fila(self, diretorio_tmp) -> None:
        banco = _banco_com_linhas(diretorio_tmp)
        correcao = corrigir_linha(
            banco, "linha-baixa", "Illm. Snr. Presidente", usuario="ana", observacao="revisão visual"
        )
        assert correcao.origem == "humana"
        assert listar_fila(banco) == []
        engine = inicializar_banco(banco)
        with fabrica_sessoes(engine)() as sessao:
            linha = sessao.get(Linha, "linha-baixa")
            registro = sessao.scalar(select(Correcao).where(Correcao.id == correcao.id))
            assert linha.texto_diplomatico == "Illm. Snr. Presidente"
            assert linha.status_revisao == "revisada"
            assert registro.texto_anterior == "Illm. Snr."

    def test_marcar_treinamento_e_selecao_ativa(self, diretorio_tmp) -> None:
        banco = _banco_com_linhas(diretorio_tmp)
        marcar_linha(banco, "linha-baixa", "treinamento", usuario="ana")
        assert listar_fila(banco) == []
        candidatos = selecionar_linhas(banco)
        assert candidatos == []
        todos = selecionar_linhas(banco, incluir_revisadas=True)
        assert todos[0].linha_id == "linha-alta" or todos[0].linha_id == "linha-baixa"

    def test_validacoes_de_entrada(self, diretorio_tmp) -> None:
        banco = _banco_com_linhas(diretorio_tmp)
        with pytest.raises(ValueError, match="Origem inválida"):
            corrigir_linha(banco, "linha-baixa", "x", origem="inventada")
        with pytest.raises(ValueError, match="Status permitido"):
            marcar_linha(banco, "linha-baixa", "qualquer")
        with pytest.raises(ValueError, match="não pode ser vazio"):
            corrigir_linha(banco, "linha-baixa", "")


class TestDataset:
    def test_inicia_exporta_valida_e_reexporta_idempotente(self, diretorio_tmp) -> None:
        banco = _banco_com_linhas(diretorio_tmp)
        marcar_linha(banco, "linha-baixa", "treinamento")
        base = iniciar_dataset("cartas 1891", diretorio_tmp / "colecoes")
        resultado = exportar_linhas_revisadas(banco, base)
        assert resultado.adicionadas == 1
        assert resultado.ignoradas == 0
        assert len(list((base / "imagens").iterdir())) == 1
        assert len((base / "transcricoes").glob("*.txt").__iter__().__next__().read_text()) > 0
        assert validar_dataset(base) == []
        segunda = exportar_linhas_revisadas(banco, base)
        assert segunda.adicionadas == 0
        assert segunda.ignoradas == 1

    def test_valida_manifesto_invalido(self, diretorio_tmp) -> None:
        base = iniciar_dataset("ruim", diretorio_tmp)
        (base / "manifest.jsonl").write_text(json.dumps({"id": "x"}) + "\n", encoding="utf-8")
        erros = validar_dataset(base)
        assert any("imagem não encontrada" in erro for erro in erros)
        assert any("transcrição não encontrada" in erro for erro in erros)

    def test_split_por_documento_sem_vazamento(self, diretorio_tmp) -> None:
        manifesto = diretorio_tmp / "manifest.jsonl"
        registros = [
            {"id": "a1", "documento": "a", "escrevente": "x"},
            {"id": "a2", "documento": "a", "escrevente": "x"},
            {"id": "b1", "documento": "b", "escrevente": "y"},
            {"id": "c1", "documento": "c", "escrevente": "z"},
        ]
        manifesto.write_text("".join(json.dumps(r) + "\n" for r in registros), encoding="utf-8")
        destino = diretorio_tmp / "splits"
        contagem = dividir_manifesto(manifesto, destino, proporcoes=(0.34, 0.33, 0.33))
        assert sum(contagem.values()) == 4
        grupos = {}
        for conjunto in ("treino", "validacao", "teste"):
            dados = [json.loads(x) for x in (destino / conjunto / "manifest.jsonl").read_text().splitlines() if x]
            for item in dados:
                assert item["documento"] not in grupos or grupos[item["documento"]] == conjunto
                grupos[item["documento"]] = conjunto
