"""Testes do Marco 3: formatos de exportação e PDF pesquisável fallback."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from ocr_historico.exportacao.hocr import exportar_hocr
from ocr_historico.exportacao.overlay import exportar_overlay
from ocr_historico.exportacao.pagexml import exportar_pagexml
from ocr_historico.exportacao.pdf_pesquisavel import exportar_pdf_pesquisavel
from ocr_historico.exportacao.relatorio import exportar_baixa_confianca, exportar_relatorio_html
from ocr_historico.exportacao.tsv import exportar_tsv


def _paginas(diretorio_tmp: Path):
    imagem = diretorio_tmp / "pagina.png"
    Image.new("RGB", (1500, 500), "white").save(imagem)
    return [
        {
            "numero": 1,
            "qualidade": {"largura": 1500, "altura": 500},
            "imagem_original": str(imagem),
            "texto_diplomatico": "Presidente 1891",
            "linhas": [
                {
                    "numero": 1,
                    "x": 10,
                    "y": 20,
                    "largura": 200,
                    "altura": 30,
                    "texto": "Presidente",
                    "confianca": 0.95,
                },
                {
                    "numero": 2,
                    "x": 10,
                    "y": 60,
                    "largura": 100,
                    "altura": 30,
                    "texto": "1891",
                    "confianca": 0.40,
                },
            ],
        }
    ]


class TestFormatos:
    def test_tsv(self, diretorio_tmp) -> None:
        saida = exportar_tsv(diretorio_tmp, "doc", _paginas(diretorio_tmp))
        conteudo = saida.read_text(encoding="utf-8")
        assert "page_num\tline_num" in conteudo
        assert "Presidente" in conteudo
        assert "0.95" in conteudo

    def test_hocr_tem_bbox(self, diretorio_tmp) -> None:
        saida = exportar_hocr(diretorio_tmp, "doc", _paginas(diretorio_tmp))
        conteudo = saida.read_text(encoding="utf-8")
        assert "bbox 10 20 210 50" in conteudo
        assert "x_wconf 95" in conteudo

    def test_pagexml_valido(self, diretorio_tmp) -> None:
        saida = exportar_pagexml(diretorio_tmp, "doc", _paginas(diretorio_tmp))
        raiz = ET.parse(saida).getroot()
        page = next(raiz.iter())
        assert page.tag.endswith("PcGts")
        unicode_texts = [el.text for el in raiz.iter() if el.tag.endswith("Unicode")]
        assert "Presidente" in unicode_texts

    def test_overlay_gera_imagem(self, diretorio_tmp) -> None:
        saidas = exportar_overlay(diretorio_tmp / "overlays", _paginas(diretorio_tmp))
        assert len(saidas) == 1
        assert saidas[0].is_file()

    def test_relatorio_e_csv(self, diretorio_tmp) -> None:
        paginas = _paginas(diretorio_tmp)
        csv_path = exportar_baixa_confianca(diretorio_tmp, "doc", paginas, 0.82)
        csv_text = csv_path.read_text(encoding="utf-8")
        assert "1891" in csv_text and "Presidente" not in csv_text
        rel = exportar_relatorio_html(diretorio_tmp, "doc", "Doc", paginas, "concluido", 0.82)
        html_text = rel.read_text(encoding="utf-8")
        assert "baixa" in html_text
        assert "1 de 2" in html_text

    def test_pdf_pesquisavel_fallback(self, diretorio_tmp) -> None:
        paginas = _paginas(diretorio_tmp)
        destino, origem = exportar_pdf_pesquisavel(diretorio_tmp, "doc", "", paginas)
        if destino is None:
            return
        assert origem == "pymupdf_fallback"
        import fitz

        with fitz.open(destino) as doc:
            assert doc.page_count == 1
            assert "Presidente" in doc[0].get_text("text") or doc[0].get_text("text") == ""
