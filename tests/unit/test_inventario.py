"""Testes do inventário determinístico e da preservação verificável."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from ocr_historico.ingestao.hash import calcular_sha256
from ocr_historico.ingestao.inventario import inventariar_entrada, salvar_inventario
from ocr_historico.ingestao.preservacao import preservar_original


def _arvore(base: Path) -> None:
    (base / "sub").mkdir(parents=True)
    (base / "a.pdf").write_bytes(b"%PDF-1.4 fake")
    (base / "sub" / "b.png").write_bytes(b"png")
    (base / ".oculto.png").write_bytes(b"x")
    (base / "nota.txt").write_text("fora", encoding="utf-8")
    (base / "temp.jpg~").write_bytes(b"y")


class TestInventario:
    def test_recursivo_deterministico_e_ignorados(self, diretorio_tmp: Path) -> None:
        base = diretorio_tmp / "entrada"
        base.mkdir()
        _arvore(base)
        inv = inventariar_entrada(base)
        assert len(inv.itens) == 5
        assert len(inv.suportados) == 2
        assert len(inv.ignorados) == 3
        motivos = {i.motivo_ignorado for i in inv.ignorados}
        assert "oculto" in motivos and "formato_nao_suportado" in motivos
        ordens = [i.caminho_relativo for i in inv.itens]
        assert ordens == sorted(ordens)
        assert [i.caminho_relativo for i in inv.itens] == [
            i.caminho_relativo for i in inventariar_entrada(base).itens
        ]

    def test_hashes_e_arquivo_unico(self, diretorio_tmp: Path) -> None:
        alvo = diretorio_tmp / "unico.pdf"
        alvo.write_bytes(b"%PDF-1.4 unico")
        inv = inventariar_entrada(alvo)
        assert len(inv.suportados) == 1
        assert inv.suportados[0].sha256 == calcular_sha256(alvo)
        assert inv.suportados[0].caminho_relativo == "unico.pdf"

    def test_salvar_json_e_csv(self, diretorio_tmp: Path) -> None:
        base = diretorio_tmp / "entrada"
        base.mkdir()
        (base / "c.png").write_bytes(b"png")
        inv = inventariar_entrada(base)
        saida = salvar_inventario(inv, diretorio_tmp / "inv")
        dados = json.loads(saida["json"].read_text(encoding="utf-8"))
        assert dados["resumo"]["suportados"] == 1
        assert (saida["csv"].stat().st_size) > 0


class TestPreservacao:
    def test_copia_verificada_e_idempotente(self, diretorio_tmp: Path) -> None:
        origem_dir = diretorio_tmp / "entrada"
        origem_dir.mkdir()
        alvo = origem_dir / "carta.png"
        Image.new("RGB", (50, 50), "white").save(alvo)
        item = inventariar_entrada(alvo).suportados[0]
        destino = diretorio_tmp / "preservado"
        primeiro = preservar_original(item, destino, modo="copy")
        assert primeiro.copiado is True and primeiro.verificado is True
        assert (destino / "carta.png").is_file()
        segundo = preservar_original(item, destino, modo="copy")
        assert segundo.copiado is False and segundo.verificado is True
        assert alvo.read_bytes() == (destino / "carta.png").read_bytes()

    def test_content_addressed(self, diretorio_tmp: Path) -> None:
        origem = diretorio_tmp / "doc.pdf"
        origem.write_bytes(b"%PDF-1.4 x")
        item = inventariar_entrada(origem).suportados[0]
        destino = diretorio_tmp / "ca"
        resultado = preservar_original(item, destino, modo="content_addressed")
        assert resultado.copiado is True
        esperado = destino / "sha256" / item.sha256[:2] / item.sha256 / "doc.pdf"
        assert esperado.is_file()