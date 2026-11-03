"""Adaptador Kraken (HTR/segmentação de manuscritos), CPU-first e degradável."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image

from ..layout.linhas import segmentar_linhas
from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina

MENSAGEM_INSTALACAO = (
    "Kraken não instalado. Instale com 'pip install kraken' (extra htr) e baixe um modelo "
    "com 'ocrhist treinar kraken --help' ou coloque o .mlmodel em data/modelos/kraken/. "
    "O recurso de manuscrito fica desabilitado; o lote continua com os motores disponíveis."
)
MENSAGEM_MODELO = (
    "Kraken instalado, mas nenhum modelo HTR .mlmodel encontrado em data/modelos/kraken/ "
    "nem em --modelo (blla.mlmodel, se presente, serve só à segmentação de linhas). "
    "Treine com 'ocrhist treinar kraken --help' ou copie o .mlmodel treinado para "
    "data/modelos/kraken/. Use --modelo para apontar um arquivo local."
)


def _tem_kraken() -> bool:
    return importlib.util.find_spec("kraken") is not None


def _dir_modelos() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "modelos" / "kraken"


def _modelos_htr() -> list[Path]:
    """Modelos de reconhecimento (.mlmodel) — exclui segmentação (blla*)."""
    base = _dir_modelos()
    if not base.is_dir():
        return []
    return sorted(
        p
        for p in base.glob("*.mlmodel")
        if p.is_file() and not p.stem.lower().startswith(("blla", "segmentation"))
    )


def _tem_modelo_htr() -> bool:
    return bool(_modelos_htr())


def _modelo_path(config: RecognitionConfig) -> Path | None:
    # config.modelo pode ser caminho ou nome; tenta resolver
    candidatos: list[Path] = []
    if config.modelo and config.modelo not in {"best", "default"}:
        p = Path(config.modelo)
        if p.is_file():
            return p
        # tenta relativo a data/modelos/kraken
        raiz = Path(__file__).resolve().parents[3]
        candidatos.append(raiz / "data" / "modelos" / "kraken" / config.modelo)
        candidatos.append(raiz / "data" / "modelos" / "kraken" / f"{config.modelo}.mlmodel")
    raiz = Path(__file__).resolve().parents[3]
    for nome in ("modelo.mlmodel", "htr.mlmodel", "kraken.mlmodel", "por_handwritten.mlmodel"):
        candidatos.append(raiz / "data" / "modelos" / "kraken" / nome)
    # também verifica diretamente data/modelos/kraken/*.mlmodel (blla é segmentação, não HTR)
    for cand in candidatos:
        if cand.is_file():
            return cand
    htr = _modelos_htr()
    return htr[0] if htr else None


class KrakenEngine(MotorPagina):
    """HTR para manuscritos. Nunca baixa modelo silenciosamente."""

    name = "kraken"

    def available(self) -> bool:
        """Pacote instalado E modelo HTR presente (blla não conta: é segmentação)."""
        return _tem_kraken() and _tem_modelo_htr()

    def _reconhecer_via_kraken(self, imagem: Image.Image, modelo: Path) -> list[str]:
        """Chama Kraken 6/7 com uma segmentação bbox de uma linha."""
        try:
            from kraken import rpred  # type: ignore[import-not-found]
            from kraken.containers import BBoxLine, Segmentation  # type: ignore[import-not-found]
            from kraken.lib import models as km  # type: ignore[import-not-found]

            net = km.load_any(str(modelo))
            largura, altura = imagem.size
            bounds = Segmentation(
                type="bbox",
                imagename="",
                text_direction="horizontal-lr",
                script_detection=False,
                lines=[
                    BBoxLine(
                        id="line-1",
                        bbox=(0, 0, largura, altura),
                        text_direction="horizontal-lr",
                    )
                ],
            )
            preds = list(rpred.rpred(net, imagem, bounds))  # type: ignore[attr-defined]
            textos: list[str] = []
            for p in preds:
                if isinstance(p, dict) and "prediction" in p:
                    textos.append(str(p["prediction"]))
                elif hasattr(p, "prediction"):
                    textos.append(str(p.prediction))
                elif isinstance(p, (list, tuple)) and p:
                    textos.append(str(p[0]))
                else:
                    textos.append(str(p))
            return textos
        except Exception as exc:  # noqa: BLE001
            raise MotorIndisponivel(f"Falha ao carregar/reconhecer modelo Kraken {modelo}: {exc}") from exc

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        if not _tem_kraken():
            raise MotorIndisponivel(MENSAGEM_INSTALACAO)
        modelo = _modelo_path(config)
        if modelo is None:
            raise MotorIndisponivel(MENSAGEM_MODELO)
        caminho = Path(image_path)
        if not caminho.is_file():
            raise MotorIndisponivel(f"Imagem não encontrada para Kraken: {caminho}")
        # segmenta
        seg = segmentar_linhas(caminho, preferencia="kraken")
        linhas: list[LinhaRec] = []
        try:
            with Image.open(caminho) as pil:
                pil_rgba = pil.convert("RGB")
                # recorta por caixa quando há segmentação
                if seg.linhas:
                    for caixa in seg.linhas:
                        x, y, w, h = caixa.x, caixa.y, caixa.largura, caixa.altura
                        recorte = pil_rgba.crop((x, y, x + w, y + h))
                        textos = self._reconhecer_via_kraken(recorte, modelo)
                        texto = textos[0] if textos else ""
                        linhas.append(
                            LinhaRec(
                                numero=caixa.numero,
                                x=x,
                                y=y,
                                largura=w,
                                altura=h,
                                texto=texto,
                                confianca=None,
                            )
                        )
                else:
                    textos = self._reconhecer_via_kraken(pil_rgba, modelo)
                    # sem segmentação, linha única cobrindo página
                    w, h = pil_rgba.size
                    linhas = [
                        LinhaRec(
                            numero=1,
                            x=0,
                            y=0,
                            largura=w,
                            altura=h,
                            texto=textos[0] if textos else "",
                            confianca=None,
                        )
                    ]
        except MotorIndisponivel:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MotorIndisponivel(f"Falha no reconhecimento Kraken: {exc}") from exc
        bruto = "\n".join(ln.texto for ln in linhas)
        aviso = seg.aviso if seg.metodo == "fallback" else None
        return ResultadoPagina(
            texto_bruto=bruto,
            linhas=tuple(linhas),
            confianca_media=None,
            motor=self.name,
            aviso=aviso,
        )

    def recognize_lines(self, lines: list[Path | str], config: RecognitionConfig) -> list[ResultadoPagina]:
        if not _tem_kraken():
            raise MotorIndisponivel(MENSAGEM_INSTALACAO)
        modelo = _modelo_path(config)
        if modelo is None:
            raise MotorIndisponivel(MENSAGEM_MODELO)
        resultados: list[ResultadoPagina] = []
        for idx, p in enumerate(lines, start=1):
            try:
                res = self.recognize_page(p, config, numero_pagina=idx)
            except MotorIndisponivel as exc:
                resultados.append(
                    ResultadoPagina(texto_bruto="", linhas=(), motor=self.name, aviso=str(exc))
                )
                continue
            resultados.append(res)
        return resultados
