"""Integração do fluxo profissional: motores, fila de OCR, produtos/download."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from test_upload_web import _png_bytes, _servidor

from ocr_historico.web.app import Manipulador


def _get(servidor, rota: str) -> tuple[int, dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{servidor.server_port}{rota}", timeout=10) as r:
        return r.status, json.loads(r.read().decode())


def _post_json(servidor, rota: str, carga: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{servidor.server_port}{rota}",
        data=json.dumps(carga).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_motores_lista_e_recomendado(tmp_path: Path) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        codigo, resp = _get(servidor, "/api/motores")
        assert codigo == 200
        nomes = {m["nome"] for m in resp["motores"]}
        assert {"tesseract", "paddleocr", "kraken"} <= nomes
        assert all("disponivel" in m for m in resp["motores"])
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_status_olmocr_na_gui(tmp_path: Path, monkeypatch) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        from ocr_historico.web.paddle_vl import GERENCIADOR

        monkeypatch.setattr(GERENCIADOR, "_online", lambda base: (True, ["Qwen3VL-8B-Instruct"]))
        codigo, resp = _get(servidor, "/api/paddle-vl?motor=olmocr")
        assert codigo == 200
        assert resp["motor"] == "olmocr"
        assert resp["online"] is True
        assert "olmocr" in resp["mensagem"]
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_processar_enfileira_e_conclui(tmp_path: Path) -> None:
    servidor, cfg = _servidor(tmp_path)
    try:
        from ocr_historico.ingestao import ingerir_entrada

        alvo = Path(cfg.entrada) / "doc.png"
        alvo.write_bytes(_png_bytes())
        resumo = ingerir_entrada(Path(cfg.entrada), cfg)
        assert resumo.novos == 1

        codigo, resp = _post_json(servidor, "/api/processar", {"retry_failed": True})
        assert codigo == 200 and resp["ok"] is True

        for _ in range(300):
            _, snap = _get(servidor, "/api/trabalho")
            if snap["estado"] in {"concluido", "erro", "cancelado"}:
                break
            time.sleep(0.2)
        assert snap["estado"] == "concluido", snap
        assert snap["percentual"] == 100
        assert snap["resumo"]["paginas_ok"] + snap["resumo"]["paginas_erro"] >= 1

        # segunda chamada imediata após conclusão pode iniciar de novo (ocioso)
        codigo2, _ = _post_json(servidor, "/api/processar", {"ids": resumo.documentos})
        assert codigo2 == 200
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_processar_concorrente_retorna_409(tmp_path: Path) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        from ocr_historico.web.trabalho import FILA

        FILA._estado = "rodando"  # simula OCR em andamento sem gastar CPU
        try:
            codigo, resp = _post_json(servidor, "/api/processar", {})
            assert codigo == 409 and "andamento" in resp["erro"]
        finally:
            FILA._estado = "ocioso"
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_produtos_e_download_confinado(tmp_path: Path) -> None:
    servidor, cfg = _servidor(tmp_path)
    try:
        from ocr_historico.ingestao import ingerir_entrada

        (Path(cfg.entrada) / "doc.png").write_bytes(_png_bytes())
        resumo = ingerir_entrada(Path(cfg.entrada), cfg)
        doc_id = resumo.documentos[0]

        codigo, antes = _get(servidor, f"/api/produtos?id={doc_id}")
        assert codigo == 200 and antes["arquivos"] == []

        # download fora da pasta é recusado mesmo sem produtos
        try:
            _get(servidor, f"/api/download?id={doc_id}&arquivo=..%2Fsegredo.txt")
            raise AssertionError("deveria recusar traversal")
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        Manipulador.config_app = cfg
        servidor.shutdown()
        servidor.server_close()
