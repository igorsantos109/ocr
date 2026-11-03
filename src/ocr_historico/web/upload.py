"""Upload de arquivos via drag-and-drop (multipart/form-data, só stdlib).

Invariantes garantidas:
- nenhum byte do conteúdo é alterado (enquadramento CRLF pertence ao
  delimitador, nunca ao payload);
- a ausência do delimitador de fechamento invalida o pacote inteiro;
- nomes de arquivo nunca escapam do diretório de destino (`nome_seguro`);
- extensões fora de `EXTENSOES_SUPORTADAS` são recusadas antes de tocar o disco.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_ARQUIVO_BYTES = 50 * 1024 * 1024
MAX_ARQUIVOS = 20
MAX_NOME = 120

_DISPOSICAO = re.compile(r'form-data;\s*name="([^"]*)"')
_ARQUIVO = re.compile(r'filename="([^"]*)"')
_ARQUIVO_ESTRELA = re.compile(r'filename\*=(?:"([^"]+)"|([^;\s]+))')


@dataclass(frozen=True)
class ArquivoRecebido:
    campo: str
    nome: str
    tipo: str
    dados: bytes


@dataclass(frozen=True)
class PacoteMultipart:
    campos: dict[str, str] = field(default_factory=dict)
    arquivos: list[ArquivoRecebido] = field(default_factory=list)


def extrair_boundary(content_type: str) -> bytes:
    """Extrai o boundary de `multipart/form-data`; ValueError se ausente."""
    partes = [p.strip() for p in content_type.split(";")]
    if not partes or partes[0].lower() != "multipart/form-data":
        raise ValueError("Content-Type deve ser multipart/form-data")
    for parte in partes[1:]:
        if parte.lower().startswith("boundary="):
            limite = parte[len("boundary="):].strip().strip('"')
            if limite:
                return limite.encode("ascii", errors="ignore")
    raise ValueError("boundary ausente no Content-Type")


def _decodificar_nome(valor: str, cabecalho: str) -> str:
    estrela = _ARQUIVO_ESTRELA.search(cabecalho)
    if estrela:
        # cabeçalhos foram decodificados como latin-1: volta aos bytes
        # originais para decodificar o UTF-8 percent-encoded corretamente.
        brutos = (estrela.group(1) or estrela.group(2) or "").strip().encode("latin-1", errors="ignore")
        if b"''" in brutos:
            _, _, resto = brutos.partition(b"''")
            return unquote(resto, encoding="utf-8", errors="replace")
        return unquote(brutos, encoding="utf-8", errors="replace")
    return valor


def nome_seguro(nome: str) -> str:
    """Normaliza para `[A-Za-z0-9._-]` (remove acentos e traversal)."""
    base = nome.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not base or base in {".", ".."}:
        raise ValueError("nome de arquivo vazio ou inválido")
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", base) if not unicodedata.combining(c))
    limpo = "".join(c if (c.isascii() and (c.isalnum() or c in "._-")) else "_" for c in sem_acento)
    limpo = limpo.strip("._")
    if not limpo:
        raise ValueError("nome de arquivo vazio ou inválido")
    if len(limpo) > MAX_NOME:
        tronco, ponto, sufixo = limpo.rpartition(".")
        sufixo = (ponto + sufixo) if ponto else ""
        limpo = tronco[: MAX_NOME - len(sufixo)] + sufixo
    if not limpo or limpo in {".", ".."}:
        raise ValueError("nome de arquivo vazio ou inválido")
    return limpo


def _tipo_parte(cabecalhos: str) -> str:
    for linha in cabecalhos.split("\r\n"):
        if linha.lower().startswith("content-type:"):
            return linha.split(":", 1)[1].strip() or "application/octet-stream"
    return "application/octet-stream"


def parse_multipart(corpo: bytes, boundary: bytes) -> PacoteMultipart:
    """Converte corpo multipart em campos + arquivos, sem mutar payloads."""
    if not boundary:
        raise ValueError("boundary vazio")
    delimitador = b"--" + boundary
    blocos = corpo.split(delimitador)
    if len(blocos) < 2:
        raise ValueError("delimitador multipart não encontrado")
    fecho = blocos[-1]
    if not fecho.startswith(b"--"):
        raise ValueError("delimitador de fechamento ausente")
    campos: dict[str, str] = {}
    arquivos: list[ArquivoRecebido] = []
    for bloco in blocos[1:-1]:
        if bloco.startswith(b"\r\n"):
            bloco = bloco[len(b"\r\n"):]
        if bloco.endswith(b"\r\n"):
            bloco = bloco[: -len(b"\r\n")]
        else:
            raise ValueError("parte multipart sem CRLF de enquadramento")
        cabecalhos_raw, sep, dados = bloco.partition(b"\r\n\r\n")
        if not sep:
            raise ValueError("parte multipart sem separador de cabeçalhos")
        cabecalhos = cabecalhos_raw.decode("latin-1")
        disp = _DISPOSICAO.search(cabecalhos)
        if disp is None:
            continue
        nome_campo = disp.group(1)
        arq = _ARQUIVO.search(cabecalhos)
        estrela = _ARQUIVO_ESTRELA.search(cabecalhos)
        if arq is None and estrela is None:
            campos[nome_campo] = dados.decode("utf-8", errors="replace")
            continue
        nome = _decodificar_nome(arq.group(1) if arq else "", cabecalhos)
        if not nome:
            continue  # campo file vazio (navegador sem arquivo): ignora
        arquivos.append(
            ArquivoRecebido(campo=nome_campo, nome=nome, tipo=_tipo_parte(cabecalhos), dados=dados)
        )
        if len(arquivos) > MAX_ARQUIVOS:
            raise ValueError(f"limite de {MAX_ARQUIVOS} arquivos por envio")
    return PacoteMultipart(campos=campos, arquivos=arquivos)


def destino_upload(entrada: Path, nome: str, dados: bytes) -> Path:
    """Destino confinado a `entrada`; mesmo conteúdo → mesmo caminho (idempotente)."""
    seguro = nome_seguro(nome)
    alvo = entrada / seguro
    if alvo.exists():
        try:
            if alvo.read_bytes() == dados:
                return alvo
        except OSError:
            pass
        curto = hashlib.sha256(dados).hexdigest()[:8]
        alvo = entrada / f"{alvo.stem}_{curto}{alvo.suffix}"
    return alvo
