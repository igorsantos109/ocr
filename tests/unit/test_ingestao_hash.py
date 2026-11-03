"""Testes do Marco 1: SHA-256 por streaming."""

from __future__ import annotations

import hashlib

from ocr_historico.ingestao.hash import calcular_sha256


class TestHash:
    def test_confere_com_hashlib(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "doc.bin"
        alvo.write_bytes(b"conteudo historico" * 1000)
        assert calcular_sha256(alvo) == hashlib.sha256(alvo.read_bytes()).hexdigest()

    def test_arquivo_vazio_tem_hash_conhecido(self, diretorio_tmp) -> None:
        alvo = diretorio_tmp / "vazio.txt"
        alvo.write_bytes(b"")
        assert calcular_sha256(alvo) == hashlib.sha256(b"").hexdigest()
