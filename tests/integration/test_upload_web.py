"""Integração do drag-and-drop: POST /api/upload de ponta a ponta."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from ocr_historico.config import AppConfig
from ocr_historico.web.app import Manipulador

BOUNDARY = "FRONTEIRA-TESTE-99"


def _png_bytes(largura: int = 200, altura: int = 80) -> bytes:
    import io

    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "white").save(buf, format="PNG")
    return buf.getvalue()


def _corpo(partes: list[tuple[str, str | None, bytes]]) -> bytes:
    # montagem explícita para não mascarar erros de enquadramento
    corpo = b""
    for campo, nome, dados in partes:
        disp = f'form-data; name="{campo}"'
        if nome is not None:
            disp += f'; filename="{nome}"'
        corpo += (
            f"--{BOUNDARY}\r\nContent-Disposition: {disp}\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("latin-1") + dados + b"\r\n"
    return corpo + f"--{BOUNDARY}--\r\n".encode("latin-1")


def _servidor(tmp_path: Path) -> tuple[ThreadingHTTPServer, AppConfig]:
    entrada = tmp_path / "entrada"
    entrada.mkdir(exist_ok=True)
    cfg = AppConfig(entrada=entrada, saida=tmp_path / "saida", banco=tmp_path / "up.sqlite3")
    Manipulador.banco = cfg.banco
    Manipulador.config_app = cfg
    Manipulador.config_llm = {"enabled": False, "model": ""}
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, cfg


def _post(servidor: ThreadingHTTPServer, corpo: bytes, content_type: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{servidor.server_port}/api/upload",
        data=corpo,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_upload_png_registra_documento(tmp_path: Path) -> None:
    servidor, cfg = _servidor(tmp_path)
    try:
        codigo, resp = _post(
            servidor,
            _corpo([("arquivo", "carta.png", _png_bytes())]),
            f"multipart/form-data; boundary={BOUNDARY}",
        )
        assert codigo == 200
        assert resp["novos"] == 1 and resp["pulados"] == 0
        assert len(resp["ids"]) == 1
        assert resp["arquivos"][0]["status"] == "ok"
        salvo = Path(cfg.entrada) / "upload_web" / "carta.png"
        assert salvo.is_file()
        from sqlalchemy import select

        from ocr_historico.database import fabrica_sessoes, inicializar_banco
        from ocr_historico.models import Documento

        with fabrica_sessoes(inicializar_banco(cfg.banco))() as s:
            doc = s.scalars(select(Documento)).one()
            assert doc.status == "aguardando_ocr" and doc.nome_original == "carta.png"
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_reenvio_mesmo_bytes_idempotente(tmp_path: Path) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        corpo = _corpo([("arquivo", "carta.png", _png_bytes())])
        ct = f"multipart/form-data; boundary={BOUNDARY}"
        codigo, r1 = _post(servidor, corpo, ct)
        assert codigo == 200 and r1["novos"] == 1
        codigo, r2 = _post(servidor, corpo, ct)
        assert codigo == 200 and r2["novos"] == 0 and r2["pulados"] == 1
        assert r1["ids"] == r2["ids"]
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_tipos_recusados_sem_tocar_disco(tmp_path: Path) -> None:
    servidor, cfg = _servidor(tmp_path)
    try:
        codigo, resp = _post(
            servidor,
            _corpo([("arquivo", "virus.exe", b"MZ..."), ("arquivo", "../../fuga.png", _png_bytes())]),
            f"multipart/form-data; boundary={BOUNDARY}",
        )
        assert codigo == 200 and resp["novos"] == 1
        por_nome = {a["nome"]: a for a in resp["arquivos"]}
        assert por_nome["virus.exe"]["status"] == "erro"
        assert (Path(cfg.entrada) / "upload_web" / "fuga.png").is_file()
        assert not (Path(cfg.entrada) / "upload_web" / "virus.exe").exists()
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_arquivo_vazio_e_sem_arquivo(tmp_path: Path) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        codigo, resp = _post(
            servidor, _corpo([("arquivo", "vazio.png", b"")]), f"multipart/form-data; boundary={BOUNDARY}"
        )
        assert codigo == 200 and resp["arquivos"][0]["status"] == "erro"
        codigo, resp = _post(
            servidor, _corpo([("nada", None, b"1")]), f"multipart/form-data; boundary={BOUNDARY}"
        )
        assert codigo == 400
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_content_type_invalido_400(tmp_path: Path) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        codigo, _ = _post(servidor, b"{}", "application/json")
        assert codigo == 400
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_limite_total_413(monkeypatch, tmp_path: Path) -> None:
    import ocr_historico.web.upload as up_mod

    monkeypatch.setattr(up_mod, "MAX_TOTAL_BYTES", 100)
    servidor, _ = _servidor(tmp_path)
    try:
        codigo, resp = _post(
            servidor, _corpo([("arquivo", "a.png", b"x" * 200)]), f"multipart/form-data; boundary={BOUNDARY}"
        )
        assert codigo == 413 and "limite" in resp["erro"]
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_limite_por_arquivo(monkeypatch, tmp_path: Path) -> None:
    import ocr_historico.web.upload as up_mod

    monkeypatch.setattr(up_mod, "MAX_ARQUIVO_BYTES", 10)
    servidor, _ = _servidor(tmp_path)
    try:
        codigo, resp = _post(
            servidor, _corpo([("arquivo", "a.png", b"x" * 11)]), f"multipart/form-data; boundary={BOUNDARY}"
        )
        assert codigo == 200
        assert resp["arquivos"][0]["status"] == "erro" and resp["novos"] == 0
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_processar_apos_envio(tmp_path: Path) -> None:
    servidor, _ = _servidor(tmp_path)
    try:
        codigo, resp = _post(
            servidor,
            _corpo([("arquivo", "carta.png", _png_bytes()), ("processar", None, b"1")]),
            f"multipart/form-data; boundary={BOUNDARY}",
        )
        assert codigo == 200 and resp["novos"] == 1
        assert "trabalho" in resp  # OCR passou a rodar em segundo plano
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_entrada_inacessivel_retorna_500_json(tmp_path: Path) -> None:
    """Regressão: OSError no mkdir matava a conexão (navegador: Failed to fetch)."""
    servidor, cfg = _servidor(tmp_path)
    bloqueador = tmp_path / "bloqueio"
    bloqueador.write_bytes(b"caminho ocupado por arquivo")
    Manipulador.config_app = cfg.model_copy(update={"entrada": bloqueador})
    try:
        codigo, resp = _post(
            servidor,
            _corpo([("arquivo", "carta.png", _png_bytes())]),
            f"multipart/form-data; boundary={BOUNDARY}",
        )
        assert codigo == 500 and "inacess" in resp["erro"]
    finally:
        Manipulador.config_app = cfg
        servidor.shutdown()
        servidor.server_close()
