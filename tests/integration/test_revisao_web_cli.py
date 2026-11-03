"""Integração dos endpoints de revisão e comandos de dataset."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from PIL import Image
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.models import Documento, Linha, Pagina
from ocr_historico.web.app import Manipulador

runner = CliRunner()


def _banco(diretorio_tmp):
    banco = diretorio_tmp / "b.sqlite3"
    imagem = diretorio_tmp / "linha.png"
    Image.new("RGB", (400, 100), "white").save(imagem)
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as sessao:
        doc = Documento(
            id="doc-web",
            caminho_original="/doc.pdf",
            nome_original="doc.pdf",
            sha256="e" * 64,
            tipo_arquivo="pdf",
            perfil="automatico",
            numero_paginas=1,
            status="concluido",
            configuracao_json={},
        )
        pagina = Pagina(
            id="pag-web",
            documento=doc,
            numero=1,
            imagem_original=str(imagem),
            imagem_pre_processada=str(imagem),
            largura=400,
            altura=100,
            status="concluida",
        )
        sessao.add(doc)
        sessao.flush()
        sessao.add(
            Linha(
                id="linha-web",
                pagina=pagina,
                numero=1,
                x=1,
                y=1,
                largura=100,
                altura=20,
                texto_bruto="Texto  original",
                texto_diplomatico="Texto original",
                confianca=0.3,
                exige_revisao=True,
                status_revisao="alta",
                imagem_linha=str(imagem),
            )
        )
        sessao.commit()
    return banco


def _servidor(banco):
    Manipulador.banco = banco
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


def _post(servidor, rota, corpo):
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{servidor.server_port}{rota}",
        data=json.dumps(corpo).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=10) as resposta:
        return resposta.status, json.loads(resposta.read())


class TestRevisaoWeb:
    def test_endpoint_corrige_e_marca_com_auditoria(self, diretorio_tmp) -> None:
        banco = _banco(diretorio_tmp)
        servidor = _servidor(banco)
        try:
            codigo, corpo = _post(
                servidor,
                "/api/corrigir",
                {"linha_id": "linha-web", "texto": "Texto corrigido", "usuario": "web-test"},
            )
            assert codigo == 200 and corpo["ok"] is True
            with urllib.request.urlopen(
                f"http://127.0.0.1:{servidor.server_port}/api/revisao?documento=doc-web"
            ) as resposta:
                dados = json.loads(resposta.read())
            assert dados["linhas"] == []
            codigo, corpo = _post(
                servidor,
                "/api/marcar",
                {"linha_id": "linha-web", "status": "treinamento"},
            )
            assert codigo == 200 and corpo["ok"] is True
        finally:
            servidor.shutdown()
            servidor.server_close()


class TestDatasetCLI:
    def test_comandos_iniciar_validar_e_dividir(self, diretorio_tmp) -> None:
        raiz = diretorio_tmp / "colecoes"
        iniciar = runner.invoke(app, ["dataset", "iniciar", "minha coleção", "--raiz", str(raiz)])
        assert iniciar.exit_code == 0, iniciar.output
        base = raiz / "minha_colecao" / "ground_truth"
        (base / "imagens" / "a.png").write_bytes(b"fake")
        (base / "transcricoes" / "a.gt.txt").write_text("texto", encoding="utf-8")
        (base / "manifest.jsonl").write_text(
            json.dumps(
                {
                    "id": "a",
                    "imagem": "imagens/a.png",
                    "transcricao": "transcricoes/a.gt.txt",
                    "documento": "doc-a",
                    "revisado": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        validar = runner.invoke(app, ["dataset", "validar", str(base)])
        assert validar.exit_code == 0, validar.output
        dividir = runner.invoke(app, ["dataset", "dividir", str(base), "--destino", str(raiz / "splits")])
        assert dividir.exit_code == 0, dividir.output
        assert (raiz / "splits" / "treino" / "manifest.jsonl").is_file()
