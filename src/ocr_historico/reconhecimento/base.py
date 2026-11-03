"""Interface comum dos motores de reconhecimento."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class MotorIndisponivel(Exception):
    """Motor instalado ausente ou mal configurado, com mensagem acionável."""


@dataclass(frozen=True)
class RecognitionConfig:
    engine: str = "tesseract"
    idioma: str = "por"
    oem: int = 1
    psm: int = 3
    modelo: str = "best"
    # Usados só por motores VLM locais (ex. paddle_vl); demais ignoram.
    base_url: str = ""
    timeout_segundos: int = 300
    max_lado_px: int = 1024
    dispositivo: str = "cpu"
    backend: str = "auto"
    allow_download: bool = False
    det_model_dir: str = ""
    rec_model_dir: str = ""
    cls_model_dir: str = ""
    text_detection_model_dir: str = ""
    text_recognition_model_dir: str = ""
    textline_orientation_model_dir: str = ""
    use_angle_cls: bool = True


@dataclass(frozen=True)
class LinhaRec:
    numero: int
    x: int
    y: int
    largura: int
    altura: int
    texto: str
    confianca: float | None


@dataclass(frozen=True)
class ResultadoPagina:
    texto_bruto: str
    linhas: tuple[LinhaRec, ...] = ()
    confianca_media: float | None = None
    motor: str = ""
    aviso: str | None = None
    divergencias: tuple[str, ...] = field(default=())


class RecognitionEngine(Protocol):
    name: str

    def available(self) -> bool:
        """Informa se o motor pode executar neste host, sem efeitos colaterais."""
        ...

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        """Reconhece uma página e retorna texto, linhas e confiança."""
        ...

    def recognize_lines(self, lines: list[Path | str], config: RecognitionConfig) -> list[ResultadoPagina]:
        """Reconhece recortes de linha (segmentação chega no Marco 5)."""
        ...


class MotorPagina:
    """Mixin dos motores página-a-página: recorte de linhas ainda não suportado."""

    name: str = ""

    def recognize_lines(self, lines: list[Path | str], config: RecognitionConfig) -> list[ResultadoPagina]:
        raise NotImplementedError(f"{self.name} não implementa reconhecimento por linhas")
