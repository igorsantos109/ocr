"""Descoberta recursiva de arquivos suportados, sem tocar nos originais."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("ocr_historico")

EXTENSOES_SUPORTADAS = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"})
SUFFIXOS_TEMPORARIOS = (".tmp", ".swp", ".bak", ".part", ".crdownload")


@dataclass(frozen=True)
class ArquivoDescoberto:
    caminho: Path
    nome: str
    extensao: str
    tipo_arquivo: str  # "pdf" ou "imagem"


def _e_oculto(caminho: Path) -> bool:
    return any(parte.startswith(".") for parte in caminho.parts)


def _e_temporario(caminho: Path) -> bool:
    nome = caminho.name
    if nome.startswith("~") or nome.endswith("~"):
        return True
    return caminho.suffix.lower() in SUFFIXOS_TEMPORARIOS


def tipo_por_extensao(extensao: str) -> str | None:
    ext = extensao.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return "imagem"
    return None


def descobrir_arquivos(entrada: Path | str) -> list[ArquivoDescoberto]:
    """Lista arquivos suportados a partir de um arquivo ou diretório.

    A busca é recursiva, insensível a maiúsculas/minúsculas na extensão e
    ignora arquivos ocultos, temporários e formatos não suportados, sempre
    com log explicativo. Nunca modifica os arquivos encontrados.
    """
    base = Path(entrada)
    if not base.exists():
        raise FileNotFoundError(f"Caminho de entrada não encontrado: {base}")
    candidatos: list[Path] = []
    if base.is_file():
        candidatos = [base]
    else:
        for raiz, pastas, arquivos in os.walk(base):
            pastas[:] = sorted(p for p in pastas if not p.startswith("."))
            for nome in sorted(arquivos):
                candidatos.append(Path(raiz) / nome)

    encontrados: list[ArquivoDescoberto] = []
    for caminho in candidatos:
        if _e_oculto(caminho):
            logger.info("Ignorado (oculto): %s", caminho)
            continue
        if _e_temporario(caminho):
            logger.info("Ignorado (temporário): %s", caminho)
            continue
        tipo = tipo_por_extensao(caminho.suffix)
        if tipo is None:
            logger.info("Ignorado (formato não suportado): %s", caminho)
            continue
        encontrados.append(
            ArquivoDescoberto(
                caminho=caminho,
                nome=caminho.name,
                extensao=caminho.suffix.lower(),
                tipo_arquivo=tipo,
            )
        )
    encontrados.sort(key=lambda item: str(item.caminho))
    logger.info("Descoberta: %d arquivo(s) suportado(s) em %s", len(encontrados), base)
    return encontrados
