"""Testes do Marco 1: descoberta de arquivos."""

from __future__ import annotations

from ocr_historico.ingestao.arquivos import descobrir_arquivos, tipo_por_extensao


class TestDescoberta:
    def test_extensoes_maiusculas_e_minusculas(self, diretorio_tmp) -> None:
        (diretorio_tmp / "livro.PDF").write_bytes(b"%PDF-1.4 falso")
        (diretorio_tmp / "foto.JPG").write_bytes(b"jpeg falso")
        (diretorio_tmp / "pagina.TIFF").write_bytes(b"tiff falso")
        achados = descobrir_arquivos(diretorio_tmp)
        assert {a.extensao for a in achados} == {".pdf", ".jpg", ".tiff"}
        assert all(a.tipo_arquivo in {"pdf", "imagem"} for a in achados)

    def test_ignora_ocultos_temporarios_e_nao_suportados(self, diretorio_tmp) -> None:
        (diretorio_tmp / ".oculto.png").write_bytes(b"x")
        (diretorio_tmp / "rascunho.tmp").write_bytes(b"x")
        (diretorio_tmp / "notas.txt").write_bytes(b"x")
        (diretorio_tmp / "valida.png").write_bytes(b"x")
        achados = descobrir_arquivos(diretorio_tmp)
        assert [a.nome for a in achados] == ["valida.png"]

    def test_recursivo_e_arquivo_unico(self, diretorio_tmp) -> None:
        sub = diretorio_tmp / "sub"
        sub.mkdir()
        (sub / "a.pdf").write_bytes(b"x")
        assert len(descobrir_arquivos(diretorio_tmp)) == 1
        assert len(descobrir_arquivos(sub / "a.pdf")) == 1

    def test_tipo_por_extensao(self) -> None:
        assert tipo_por_extensao(".PDF") == "pdf"
        assert tipo_por_extensao(".jpeg") == "imagem"
        assert tipo_por_extensao(".docx") is None
