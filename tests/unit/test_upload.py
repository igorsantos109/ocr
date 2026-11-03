"""Upload multipart: parser, nomes seguros e invariantes (Given/When/Then)."""

from __future__ import annotations

import random

import pytest

from ocr_historico.web.upload import (
    MAX_ARQUIVOS,
    PacoteMultipart,
    destino_upload,
    extrair_boundary,
    nome_seguro,
    parse_multipart,
)


def montar(partes: list[tuple[str, str | None, str, bytes]], boundary: str = "LIMITE---01") -> bytes:
    """Monta corpo multipart: (campo, nome_arquivo|None, content_type, dados)."""
    corpo = b""
    for campo, nome, tipo, dados in partes:
        disp = f'form-data; name="{campo}"'
        if nome is not None:
            disp += f'; filename="{nome}"'
        corpo += (
            f"--{boundary}\r\nContent-Disposition: {disp}\r\nContent-Type: {tipo}\r\n\r\n"
        ).encode("latin-1") + dados + b"\r\n"
    return corpo + f"--{boundary}--\r\n".encode("latin-1")


def test_roundtrip_arquivo_binario_com_crlf() -> None:
    # Given payload binário com CRLF e sequência parecida (mas ≠) ao boundary
    # (RFC 2046: o boundary real jamais ocorre no conteúdo)
    dados = bytes(range(256)) + b"\r\n--OUTRO-LIMITE\r\nfim"
    corpo = montar([("arq", "doc.png", "image/png", dados)])
    # When parse
    pac: PacoteMultipart = parse_multipart(corpo, b"LIMITE---01")
    # Then byte-identidade + metadados
    assert len(pac.arquivos) == 1
    rec = pac.arquivos[0]
    assert rec.dados == dados and rec.nome == "doc.png" and rec.tipo == "image/png"
    assert pac.campos == {}


def test_multiplos_arquivos_e_campo_texto() -> None:
    corpo = montar([
        ("arq", "a.png", "image/png", b"AAA"),
        ("arq", "b.pdf", "application/pdf", b"BBB"),
        ("processar", None, "text/plain", b"1"),
    ])
    pac = parse_multipart(corpo, b"LIMITE---01")
    assert [a.nome for a in pac.arquivos] == ["a.png", "b.pdf"]
    assert pac.campos == {"processar": "1"}


def test_filename_vazio_e_parte_sem_disposicao_ignorados() -> None:
    corpo = (
        b"--LIMITE---01\r\nContent-Disposition: form-data; name=\"arq\"; filename=\"\"\r\n"
        b"Content-Type: application/octet-stream\r\n\r\n\r\n"
        b"--LIMITE---01\r\nContent-Type: text/plain\r\n\r\nsem-nome\r\n"
        b"--LIMITE---01--\r\n"
    )
    pac = parse_multipart(corpo, b"LIMITE---01")
    assert pac.arquivos == []


def test_fecho_ausente_invalida_pacote() -> None:
    corpo = montar([("arq", "a.png", "image/png", b"X")])[: -len(b"--LIMITE---01--\r\n")]
    with pytest.raises(ValueError, match="fechamento"):
        parse_multipart(corpo, b"LIMITE---01")


def test_sem_delimitador_erro() -> None:
    with pytest.raises(ValueError, match="delimitador"):
        parse_multipart(b"lixo sem fronteira", b"LIMITE---01")


def test_crlf_final_ausente_erro() -> None:
    corpo = montar([("arq", "a.png", "image/png", b"X")]).replace(b"X\r\n--LIMITE", b"X--LIMITE")
    with pytest.raises(ValueError, match="CRLF"):
        parse_multipart(corpo, b"LIMITE---01")


def test_parte_sem_separador_erro() -> None:
    corpo = b"--B\r\nContent-Disposition: form-data; name=\"a\"\r\nSEM-SEPARADOR\r\n--B--\r\n"
    with pytest.raises(ValueError, match="separador"):
        parse_multipart(corpo, b"B")


def test_limite_quantidade_arquivos() -> None:
    partes = [("a", f"{i}.png", "image/png", b"x") for i in range(MAX_ARQUIVOS + 1)]
    with pytest.raises(ValueError, match="limite"):
        parse_multipart(montar(partes), b"LIMITE---01")


def test_boundary_extracao() -> None:
    assert extrair_boundary('multipart/form-data; boundary="ABC123"') == b"ABC123"
    assert extrair_boundary("multipart/form-data; boundary=XYZ") == b"XYZ"
    with pytest.raises(ValueError, match="multipart/form-data"):
        extrair_boundary("application/json")
    with pytest.raises(ValueError, match="boundary"):
        extrair_boundary("multipart/form-data")


def test_nome_seguro_traversal_e_barras() -> None:
    assert nome_seguro("../../etc/passwd.png") == "passwd.png"
    assert nome_seguro("..\\..\\janela.png") == "janela.png"
    assert nome_seguro("/absoluto/carta.png") == "carta.png"


def test_nome_seguro_acentos_e_especiais() -> None:
    assert nome_seguro("cópia (2).PDF") == "copia__2_.PDF"
    assert nome_seguro("ata reunião — final.jpg") == "ata_reuniao___final.jpg"


def test_nome_seguro_invalidos() -> None:
    for ruim in ("", "   ", ".", "..", "...", "///"):
        with pytest.raises(ValueError, match="inválido"):
            nome_seguro(ruim)


def test_nome_seguro_limite_120_preserva_extensao() -> None:
    longo = "a" * 200 + ".tiff"
    seguro = nome_seguro(longo)
    assert len(seguro) == 120 and seguro.endswith(".tiff")
    exato = "b" * 116 + ".png"  # 120 no total
    assert nome_seguro(exato) == exato


def test_filename_estrela_rfc5987_com_emoji() -> None:
    corpo = (
        b"--B\r\nContent-Disposition: form-data; name=\"arq\"; "
        b"filename*=UTF-8''carta_\xF0\x9F\x93\x9C.png\r\nContent-Type: image/png\r\n\r\nXYZ\r\n--B--\r\n"
    )
    pac = parse_multipart(corpo, b"B")
    assert pac.arquivos[0].nome == "carta_📜.png"
    assert nome_seguro(pac.arquivos[0].nome) == "carta__.png"


def test_roundtrip_pseudoaleatorio_propriedade() -> None:
    """Invariante: N pacotes aleatórios (semente fixa) sobrevivem byte a byte."""
    rng = random.Random(1891)
    for _ in range(25):
        n = rng.randint(1, 4)
        partes = []
        for i in range(n):
            dados = bytes(rng.randrange(256) for _ in range(rng.randint(0, 300)))
            partes.append((f"c{i}", f"arq{i}.png", "image/png", dados))
        pac = parse_multipart(montar(partes, "ZZZ"), b"ZZZ")
        assert len(pac.arquivos) == n
        for (_, _, _, dados), rec in zip(partes, pac.arquivos, strict=True):
            assert rec.dados == dados


def test_destino_upload_idempotente_e_confinado(tmp_path) -> None:
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    p1 = destino_upload(entrada, "carta.png", b"conteudo")
    assert p1.parent == entrada and p1.name == "carta.png"
    p1.write_bytes(b"conteudo")
    assert destino_upload(entrada, "carta.png", b"conteudo") == p1  # idempotente
    p2 = destino_upload(entrada, "carta.png", b"outro")
    assert p2 != p1 and p2.parent == entrada and p2.suffix == ".png"
    assert destino_upload(entrada, "../../fuga.png", b"x").parent == entrada
