"""Inventário determinístico de entradas e arquivos ignorados.

O inventário é independente do banco: pode ser gerado antes do OCR e serve como
registro preservável da varredura. Nenhuma operação modifica os arquivos de
entrada.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .arquivos import SUFFIXOS_TEMPORARIOS, tipo_por_extensao
from .hash import calcular_sha256


@dataclass(frozen=True)
class ItemInventario:
    caminho: str
    caminho_relativo: str
    nome: str
    extensao: str
    tipo: str | None
    suportado: bool
    tamanho_bytes: int | None
    mtime_ns: int | None
    sha256: str | None
    motivo_ignorado: str | None = None
    erro: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Inventario:
    entrada: str
    criado_em: str
    itens: tuple[ItemInventario, ...]

    @property
    def suportados(self) -> tuple[ItemInventario, ...]:
        return tuple(item for item in self.itens if item.suportado)

    @property
    def ignorados(self) -> tuple[ItemInventario, ...]:
        return tuple(item for item in self.itens if not item.suportado)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "entrada": self.entrada,
            "criado_em": self.criado_em,
            "resumo": {
                "total": len(self.itens),
                "suportados": len(self.suportados),
                "ignorados": len(self.ignorados),
            },
            "itens": [item.as_dict() for item in self.itens],
        }


def _motivo(caminho: Path) -> str | None:
    if any(parte.startswith(".") for parte in caminho.parts):
        return "oculto"
    if caminho.name.startswith("~") or caminho.name.endswith("~"):
        return "temporario"
    if caminho.suffix.lower() in SUFFIXOS_TEMPORARIOS:
        return "temporario"
    if tipo_por_extensao(caminho.suffix) is None:
        return "formato_nao_suportado"
    return None


def inventariar_entrada(
    entrada: Path | str,
    *,
    calcular_hash: bool = True,
    seguir_links: bool = False,
) -> Inventario:
    """Varre uma entrada recursivamente, de modo determinístico e auditável."""
    base = Path(entrada).expanduser()
    if not base.exists():
        raise FileNotFoundError(f"Caminho de entrada não encontrado: {base}")
    raiz = base if base.is_dir() else base.parent
    if base.is_file():
        candidatos = [base]
    else:
        candidatos = []
        for caminho in sorted(base.rglob("*"), key=lambda item: str(item)):
            if caminho.is_file() and (seguir_links or not caminho.is_symlink()):
                candidatos.append(caminho)
    itens: list[ItemInventario] = []
    for caminho in candidatos:
        try:
            relativo = caminho.relative_to(raiz).as_posix()
        except ValueError:
            relativo = caminho.name
        motivo = _motivo(caminho)
        tipo = tipo_por_extensao(caminho.suffix)
        tamanho: int | None = None
        mtime: int | None = None
        digest: str | None = None
        erro: str | None = None
        try:
            stat = caminho.stat()
            tamanho, mtime = stat.st_size, stat.st_mtime_ns
            if calcular_hash and motivo is None:
                digest = calcular_sha256(caminho)
        except OSError as exc:
            erro = str(exc)
        itens.append(
            ItemInventario(
                caminho=str(caminho.resolve()),
                caminho_relativo=relativo,
                nome=caminho.name,
                extensao=caminho.suffix.lower(),
                tipo=tipo,
                suportado=motivo is None and erro is None,
                tamanho_bytes=tamanho,
                mtime_ns=mtime,
                sha256=digest,
                motivo_ignorado=motivo,
                erro=erro,
            )
        )
    return Inventario(str(base.resolve()), datetime.now().astimezone().isoformat(), tuple(itens))


def salvar_inventario(inventario: Inventario, destino: Path | str) -> dict[str, Path]:
    """Salva JSON e CSV; escrita simples e determinística em UTF-8."""
    pasta = Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    json_path = pasta / "inventario.json"
    csv_path = pasta / "inventario.csv"
    json_path.write_text(json.dumps(inventario.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    campos = list(ItemInventario.__dataclass_fields__)
    with csv_path.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        for item in inventario.itens:
            escritor.writerow(item.as_dict())
    return {"json": json_path, "csv": csv_path}
