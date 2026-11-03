"""Testes Marco 6: revisor LLM suggest_only, sem rede real."""

from __future__ import annotations

import json

import pytest
from PIL import Image
from pydantic import ValidationError

from ocr_historico.database import fabrica_sessoes, inicializar_banco
from ocr_historico.models import Documento, Linha, Pagina
from ocr_historico.posprocessamento.llm_revisor import (
    SugestaoLLM,
    _chamar_endpoint,
    _extrair_json,
    _normalizar_tipo,
    _remover_think,
    listar_sugestoes,
    sugerir_linhas,
    validar_sugestao,
)


def test_schema_valida_e_rejeita_invalido() -> None:
    ok = {
        "texto_original": "Illm. Snr. Presldente",
        "sugestao": "Illm. Snr. Presidente",
        "tipo": "caractere",
        "justificativa_curta": "Confusão provável entre i e l.",
        "confianca": 0.86,
        "exige_revisao_visual": True,
    }
    sug = SugestaoLLM.model_validate(ok)
    assert sug.confianca == pytest.approx(0.86)
    with pytest.raises(ValidationError):
        SugestaoLLM.model_validate({**ok, "confianca": 2.0})
    with pytest.raises(ValidationError):
        SugestaoLLM.model_validate({"sugestao": "x"})  # faltam campos


def test_extrair_json_remove_cercas() -> None:
    bruto = '```json\n{"a": 1}\n```'
    assert json.loads(_extrair_json(bruto)) == {"a": 1}
    assert json.loads(_extrair_json('veja: {"a": 1} ok')) == {"a": 1}


def test_validar_sugestao_com_cerca() -> None:
    bruto = '```json\n{"texto_original": "a", "sugestao": "b", "tipo": "palavra", "confianca": 0.5}\n```'
    sug = validar_sugestao(bruto, "a")
    assert sug.sugestao == "b"


def test_remover_think_antes_do_json() -> None:
    bruto = "<think>\nPreciso responder em JSON.\n</think>\n" + '{"a": 1}'
    assert _remover_think(bruto) == '{"a": 1}'
    assert json.loads(_extrair_json(bruto)) == {"a": 1}
    sem_think = 'texto {"a": 2} fim'
    assert _remover_think(sem_think) == sem_think


def test_normalizar_tipo_mapeia_variacoes() -> None:
    assert _normalizar_tipo("confusão de caracteres") == "caractere"
    assert _normalizar_tipo("Pontuação") == "pontuacao"
    assert _normalizar_tipo("qualquer outra coisa") == "outro"
    bruto = (
        '{"texto_original": "a", "sugestao": "b", "tipo": "confusão de caracteres",'
        ' "confianca": 0.5}'
    )
    assert validar_sugestao(bruto, "a").tipo == "caractere"


def test_chamar_endpoint_chat_com_temperatura_e_limite(monkeypatch) -> None:
    import urllib.request

    registro: dict = {}

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    def _abrir(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/api/generate"):
            raise ConnectionError("sem ollama")
        registro["corpo"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _abrir)
    assert _chamar_endpoint("http://x", "m", "diga ok", 10) == "ok"
    assert registro["corpo"]["temperature"] == 0
    assert registro["corpo"]["max_tokens"] == 1024
    assert "/no_think" not in registro["corpo"]["messages"][0]["content"]
    assert _chamar_endpoint("http://x", "huihui-qwen3-8b", "diga ok", 10) == "ok"
    assert registro["corpo"]["messages"][0]["content"].endswith("/no_think")


def _banco_linha(tmp_path):
    banco = tmp_path / "llm.sqlite3"
    img = tmp_path / "p.png"
    Image.new("RGB", (200, 60), "white").save(img)
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as s:
        doc = Documento(id="d1", caminho_original="/a", nome_original="a.png", sha256="f" * 64,
                        tipo_arquivo="png", perfil="automatico", numero_paginas=1,
                        status="concluido", configuracao_json={})
        pag = Pagina(id="p1", documento=doc, numero=1, imagem_original=str(img),
                     largura=200, altura=60, status="concluida")
        s.add(doc)
        s.flush()
        s.add(Linha(id="l1", pagina=pag, numero=1, x=0, y=0, largura=200, altura=30,
                    texto_bruto="Presldente", texto_diplomatico="Presldente", confianca=0.5,
                    exige_revisao=True, status_revisao="alta"))
        s.commit()
    return banco


def test_sugerir_grava_auditoria_sem_alterar_texto(tmp_path, monkeypatch) -> None:
    import ocr_historico.posprocessamento.llm_revisor as mod

    banco = _banco_linha(tmp_path)
    payload = json.dumps({
        "texto_original": "Presldente", "sugestao": "Presidente", "tipo": "caractere",
        "justificativa_curta": "troca i/l", "confianca": 0.9, "exige_revisao_visual": True,
    })
    monkeypatch.setattr(mod, "_chamar_endpoint", lambda *a, **k: payload)
    res = sugerir_linhas(banco, ["l1"], model="teste", usuario="tester")
    assert len(res) == 1 and res[0].sugestao is not None
    assert res[0].sugestao.sugestao == "Presidente"
    # texto diplomático preservado
    engine = inicializar_banco(banco)
    with fabrica_sessoes(engine)() as s:
        from sqlalchemy import select
        linha = s.scalar(select(Linha).where(Linha.id == "l1"))
        assert linha.texto_diplomatico == "Presldente"
        assert linha.texto_bruto == "Presldente"
    sugs = listar_sugestoes(banco, "l1")
    assert len(sugs) == 1 and sugs[0].origem == "llm_sugerido"


def test_sugerir_falha_por_linha_nao_aborta(tmp_path, monkeypatch) -> None:
    import ocr_historico.posprocessamento.llm_revisor as mod

    banco = _banco_linha(tmp_path)
    monkeypatch.setattr(mod, "_chamar_endpoint", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("sem ollama")))
    res = sugerir_linhas(banco, ["l1", "inexistente"])
    assert len(res) == 2
    assert all(r.sugestao is None for r in res)


def test_sugerir_json_invalido_registra_erro(tmp_path, monkeypatch) -> None:
    import ocr_historico.posprocessamento.llm_revisor as mod

    banco = _banco_linha(tmp_path)
    monkeypatch.setattr(mod, "_chamar_endpoint", lambda *a, **k: "isto não é json {")
    res = sugerir_linhas(banco, ["l1"])
    assert res[0].sugestao is None and "inválida" in res[0].erro
