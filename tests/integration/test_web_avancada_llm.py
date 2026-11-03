"""Integração Marco 6: web avançada (imagens, 3 camadas, filtros) + CLI sugerir."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from PIL import Image
from typer.testing import CliRunner

from ocr_historico.cli import app
from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.models import Documento, Linha, Pagina
from ocr_historico.web.app import Manipulador

runner = CliRunner()


def _banco(tmp_path):
    banco = tmp_path / "web6.sqlite3"
    img = tmp_path / "pag.png"
    Image.new("RGB", (400, 200), "white").save(img)
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as s:
        doc = Documento(id="doc6", caminho_original="/d", nome_original="doc6.png", sha256="a" * 64,
                        tipo_arquivo="png", perfil="automatico", numero_paginas=1,
                        status="concluido", configuracao_json={})
        pag = Pagina(id="pag6", documento=doc, numero=1, imagem_original=str(img),
                     imagem_pre_processada=str(img), largura=400, altura=200, status="concluida")
        s.add(doc)
        s.flush()
        s.add(Linha(id="lin6a", pagina=pag, numero=1, x=10, y=10, largura=200, altura=30,
                    texto_bruto="Presldente  1891", texto_diplomatico="Presldente 1891",
                    texto_normalizado="Presidente 1891", confianca=0.6,
                    exige_revisao=True, status_revisao="alta"))
        s.add(Linha(id="lin6b", pagina=pag, numero=2, x=10, y=60, largura=200, altura=30,
                    texto_bruto="carta", texto_diplomatico="carta",
                    texto_normalizado="carta", confianca=0.95,
                    exige_revisao=False, status_revisao="baixa"))
        s.commit()
    return banco


def _servidor(banco, llm_enabled=False):
    Manipulador.banco = banco
    Manipulador.config_llm = {
        "enabled": llm_enabled, "model": "teste",
        "base_url": "http://127.0.0.1:11434", "timeout": 5,
    }
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


def _get(servidor, caminho):
    with urllib.request.urlopen(f"http://127.0.0.1:{servidor.server_port}{caminho}", timeout=10) as r:
        return r.status, r.read(), r.headers.get_content_type()


def _post(servidor, caminho, corpo):
    req = urllib.request.Request(f"http://127.0.0.1:{servidor.server_port}{caminho}",
                                 data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_pagina_imagem_e_overlay(tmp_path) -> None:
    banco = _banco(tmp_path)
    servidor = _servidor(banco)
    try:
        for tipo in ("original", "pre", "overlay"):
            codigo, corpo, ctype = _get(servidor, f"/api/pagina/imagem?id=pag6&tipo={tipo}")
            assert codigo == 200 and ctype == "image/png"
            assert corpo[:8] == b"\x89PNG\r\n\x1a\n"
        codigo, corpo, ctype = _get(servidor, "/api/linha/imagem?id=lin6a")
        assert codigo == 200 and corpo[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_linha_detalhe_tres_camadas_e_filtros(tmp_path) -> None:

    banco = _banco(tmp_path)
    servidor = _servidor(banco)
    try:
        codigo, corpo, _ = _get(servidor, "/api/linha?id=lin6a")
        dados = json.loads(corpo)
        assert dados["texto_bruto"] == "Presldente  1891"
        assert dados["texto_diplomatico"] == "Presldente 1891"
        assert dados["texto_normalizado"] == "Presidente 1891"
        # filtro por status
        codigo, corpo, _ = _get(servidor, "/api/revisao?status=alta")
        assert json.loads(corpo)["linhas"][0]["id"] == "lin6a"
        # filtro texto
        codigo, corpo, _ = _get(servidor, "/api/revisao?q=presldente")
        assert len(json.loads(corpo)["linhas"]) == 1
        # só baixa confiança
        codigo, corpo, _ = _get(servidor, "/api/revisao?baixa=1")
        ids = [item["id"] for item in json.loads(corpo)["linhas"]]
        assert "lin6a" in ids
        # llm estado
        codigo, corpo, _ = _get(servidor, "/api/llm-estado")
        assert json.loads(corpo)["enabled"] is False
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_sugerir_desabilitado_retorna_400(tmp_path) -> None:
    banco = _banco(tmp_path)
    servidor = _servidor(banco, llm_enabled=False)
    try:
        codigo, corpo = _post(servidor, "/api/sugerir", {"linha_id": "lin6a"})
        assert codigo == 400
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_sugerir_habilitado_com_mock(tmp_path, monkeypatch) -> None:
    import ocr_historico.posprocessamento.llm_revisor as mod

    banco = _banco(tmp_path)
    payload = json.dumps({"texto_original": "Presldente 1891", "sugestao": "Presidente 1891",
                          "tipo": "caractere", "justificativa_curta": "i/l", "confianca": 0.9,
                          "exige_revisao_visual": True})
    monkeypatch.setattr(mod, "_chamar_endpoint", lambda *a, **k: payload)
    servidor = _servidor(banco, llm_enabled=True)
    try:
        codigo, corpo = _post(servidor, "/api/sugerir", {"linha_id": "lin6a"})
        assert codigo == 200 and corpo["sugestao"] == "Presidente 1891"
        # ver sugestão registrada
        codigo, raw, _ = _get(servidor, "/api/linha?id=lin6a")
        assert len(json.loads(raw)["sugestoes"]) == 1
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_exportar_dataset_via_web(tmp_path, monkeypatch) -> None:
    banco = _banco(tmp_path)
    # marca linha para treinamento
    from ocr_historico.revisao import marcar_linha
    marcar_linha(banco, "lin6a", "treinamento")
    monkeypatch.chdir(tmp_path)
    servidor = _servidor(banco)
    try:
        codigo, corpo = _post(servidor, "/api/exportar-dataset", {"colecao": "web6"})
        assert codigo == 200 and corpo["adicionadas"] >= 1
        assert (tmp_path / "data" / "treinamento" / "web6" / "ground_truth" / "manifest.jsonl").is_file()
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_resumo_e_pagina_para_gui(tmp_path) -> None:
    banco = _banco(tmp_path)
    servidor = _servidor(banco)
    try:
        codigo, corpo, _ = _get(servidor, "/api/resumo")
        assert codigo == 200
        resumo = json.loads(corpo)
        assert resumo["documentos"]["total"] == 1
        assert resumo["linhas"]["fila"] == 1
        assert resumo["linhas"]["baixa_confianca"] == 1
        codigo, corpo, _ = _get(servidor, "/api/pagina?id=pag6")
        assert codigo == 200
        pagina = json.loads(corpo)
        assert pagina["numero"] == 1
        assert [(lin["numero"], lin["x"], lin["confianca"]) for lin in pagina["linhas"]] == [
            (1, 10, 0.6), (2, 10, 0.95),
        ]
        # fila traz documento para navegação direta da GUI
        codigo, corpo, _ = _get(servidor, "/api/revisao")
        item = json.loads(corpo)["linhas"][0]
        assert item["documento_id"] == "doc6" and item["pagina"] == 1
        # id ausente → 400
        try:
            _get(servidor, "/api/pagina")
            raise AssertionError("esperava HTTP 400")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_cli_sugerir_bloqueado_quando_desabilitado(tmp_path) -> None:
    cfg = tmp_path / "cfg.yaml"
    banco = tmp_path / "b.sqlite3"
    cfg.write_text(f"banco: {banco}\nllm:\n  enabled: false\n", encoding="utf-8")
    res = runner.invoke(app, ["sugerir", "--linha", "x", "--config", str(cfg)])
    assert res.exit_code == 2
    assert "desabilitado" in res.output.lower()


def test_cli_sugerir_exige_confirmacao_lote(tmp_path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("llm:\n  enabled: true\n", encoding="utf-8")
    res = runner.invoke(app, ["sugerir", "--linha", "a", "--linha", "b", "--config", str(cfg)])
    assert res.exit_code == 2
    assert "confirmar-lote" in res.output.lower()
