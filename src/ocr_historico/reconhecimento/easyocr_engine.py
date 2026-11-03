"""Adaptador EasyOCR, lazy e com modelos persistidos no workspace."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina

MENSAGEM_INSTALACAO = (
    "EasyOCR não instalado. Ative o ambiente do projeto e instale com 'pip install easyocr'."
)
MENSAGEM_MODELO = (
    "EasyOCR instalado, mas os modelos ainda não foram baixados. "
    "Execute 'bash scripts/ativar_modelos.sh' para preparar os modelos locais."
)


def _raiz() -> Path:
    return Path(__file__).resolve().parents[3]


def _dir_modelos() -> Path:
    return Path(os.environ.get("EASYOCR_MODULE_PATH", str(_raiz() / ".deps" / "models" / "easyocr")))


def _tem_easyocr() -> bool:
    return importlib.util.find_spec("easyocr") is not None


class EasyOCREngine(MotorPagina):
    """Reconhecimento impresso multilíngue com caixas e confiança."""

    name = "easyocr"
    _leitores: dict[str, object] = {}

    def available(self) -> bool:
        return _tem_easyocr()

    def _idioma(self, idioma: str) -> str:
        return {
            "por": "pt",
            "pt": "pt",
            "pt-br": "pt",
            "eng": "en",
            "en": "en",
            "spa": "es",
            "es": "es",
            "fra": "fr",
            "fr": "fr",
            "deu": "de",
            "de": "de",
        }.get(idioma.lower(), "pt")

    def _carregar(self, config: RecognitionConfig) -> object:
        if not self.available():
            raise MotorIndisponivel(MENSAGEM_INSTALACAO)
        idioma = self._idioma(config.idioma)
        chave = f"{idioma}:{config.dispositivo}"
        if chave in self._leitores:
            return self._leitores[chave]
        try:
            import easyocr  # type: ignore[import-not-found]

            leitor = easyocr.Reader(
                [idioma],
                gpu=config.dispositivo == "gpu",
                model_storage_directory=str(_dir_modelos()),
                download_enabled=config.allow_download,
                # O host não expõe AVX2; o modelo quantizado pode abortar com
                # SIGILL. O modelo FP32 é um pouco mais lento, mas seguro em CPU.
                quantize=False,
                cudnn_benchmark=False,
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001
            mensagem = str(exc)
            if "download" in mensagem.lower() or "model" in mensagem.lower():
                raise MotorIndisponivel(MENSAGEM_MODELO) from exc
            raise MotorIndisponivel(f"Falha ao iniciar EasyOCR: {exc}") from exc
        self._leitores[chave] = leitor
        return leitor

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        caminho = Path(image_path)
        if not caminho.is_file():
            raise MotorIndisponivel(f"Imagem não encontrada para EasyOCR: {caminho}")
        leitor = self._carregar(config)
        try:
            deteccoes = leitor.readtext(str(caminho), detail=1, paragraph=False)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise MotorIndisponivel(f"Falha no reconhecimento EasyOCR: {exc}") from exc
        linhas: list[LinhaRec] = []
        for idx, item in enumerate(deteccoes or [], start=1):
            try:
                poligono, texto, confianca = item[0], str(item[1]), float(item[2])
                xs = [int(float(p[0])) for p in poligono]
                ys = [int(float(p[1])) for p in poligono]
                linhas.append(
                    LinhaRec(
                        numero=idx,
                        x=min(xs),
                        y=min(ys),
                        largura=max(xs) - min(xs),
                        altura=max(ys) - min(ys),
                        texto=texto,
                        confianca=confianca,
                    )
                )
            except (IndexError, TypeError, ValueError):
                continue
        bruto = "\n".join(l.texto for l in linhas)
        confiancas = [l.confianca for l in linhas if l.confianca is not None]
        media = sum(confiancas) / len(confiancas) if confiancas else None
        return ResultadoPagina(
            texto_bruto=bruto,
            linhas=tuple(linhas),
            confianca_media=media,
            motor=self.name,
            aviso=None if linhas else "EasyOCR não detectou texto nesta página.",
        )
