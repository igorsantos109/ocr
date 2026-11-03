"""Imagens overlay numeradas para inspeção visual."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def exportar_overlay(pasta: Path, paginas: Iterable[dict]) -> list[Path]:
    destino_dir = pasta / "overlays"
    destino_dir.mkdir(parents=True, exist_ok=True)
    saidas: list[Path] = []
    try:
        fonte = ImageFont.load_default(size=16)
    except TypeError:  # Pillow anterior a 10
        fonte = ImageFont.load_default()
    for pagina in paginas:
        origem = pagina.get("imagem_pre_processada") or pagina.get("imagem_original")
        if not origem or not Path(origem).is_file():
            continue
        try:
            with Image.open(origem) as original:
                imagem = original.convert("RGB")
                desenho = ImageDraw.Draw(imagem)
                for linha in pagina.get("linhas", []):
                    x, y = int(linha.get("x", 0)), int(linha.get("y", 0))
                    w, h = int(linha.get("largura", 0)), int(linha.get("altura", 0))
                    desenho.rectangle((x, y, x + w, y + h), outline=(220, 30, 30), width=2)
                    desenho.rectangle((x, max(0, y - 20), x + 28, y), fill=(220, 30, 30))
                    desenho.text((x + 3, max(0, y - 19)), str(linha.get("numero", "?")), fill="white", font=fonte)
                destino = destino_dir / f"pagina_{int(pagina.get('numero', 0)):04d}.png"
                imagem.save(destino)
                saidas.append(destino)
        except (OSError, ValueError):
            continue
    return saidas
