"""PAGE-XML mínimo para regiões/linhas e caixas de OCR."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
ET.register_namespace("", NS)


def _pontos(x: int, y: int, largura: int, altura: int) -> str:
    return f"{x},{y} {x + largura},{y} {x + largura},{y + altura} {x},{y + altura}"


def exportar_pagexml(pasta: Path, base: str, paginas: Iterable[dict]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    raiz = ET.Element(f"{{{NS}}}PcGts")
    metadados = ET.SubElement(raiz, f"{{{NS}}}Metadata")
    ET.SubElement(metadados, f"{{{NS}}}Creator").text = "ocr-historico-br"
    page_list = ET.SubElement(raiz, f"{{{NS}}}PageList")
    for pagina in paginas:
        qualidade = pagina.get("qualidade", {})
        page = ET.SubElement(
            page_list,
            f"{{{NS}}}Page",
            {
                "imageFilename": str(pagina.get("imagem_original", "")),
                "imageWidth": str(qualidade.get("largura") or 0),
                "imageHeight": str(qualidade.get("altura") or 0),
                "pageIndex": str(pagina.get("numero", 1) - 1),
            },
        )
        regioes = ET.SubElement(page, f"{{{NS}}}TextRegion", {"id": f"r{pagina.get('numero', 0)}"})
        for linha in pagina.get("linhas", []):
            line = ET.SubElement(
                regioes, f"{{{NS}}}TextLine", {"id": f"l{pagina.get('numero', 0)}_{linha.get('numero', 0)}"}
            )
            ET.SubElement(
                line,
                f"{{{NS}}}Coords",
                {
                    "points": _pontos(
                        int(linha.get("x", 0)),
                        int(linha.get("y", 0)),
                        int(linha.get("largura", 0)),
                        int(linha.get("altura", 0)),
                    )
                },
            )
            texto = ET.SubElement(line, f"{{{NS}}}TextEquiv")
            ET.SubElement(texto, f"{{{NS}}}Unicode").text = str(linha.get("texto", ""))
            conf = linha.get("confianca")
            if conf is not None:
                texto.set("conf", str(conf))
    destino = pasta / f"{base}_page.xml"
    ET.ElementTree(raiz).write(destino, encoding="utf-8", xml_declaration=True)
    return destino
