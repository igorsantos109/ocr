"""Adaptadores opcionais para motores externos, sem downloads implícitos."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from .base import MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina


class OptionalEngine(MotorPagina):
    """Base para motores cuja dependência é opcional e lazy."""

    package_name = ""
    command_name = ""
    install_hint = ""

    def available(self) -> bool:
        return bool(
            (self.package_name and importlib.util.find_spec(self.package_name) is not None)
            or (self.command_name and shutil.which(self.command_name))
        )

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        if not self.available():
            raise MotorIndisponivel(
                f"{self.name} indisponível. Instalação explícita: {self.install_hint}. "
                "Nenhum modelo ou dado foi baixado automaticamente."
            )
        raise MotorIndisponivel(
            f"{self.name} está detectado, mas o adaptador desta versão ainda requer configuração/modelo explícito."
        )


class SuryaEngine(OptionalEngine):
    name = "surya"
    package_name = "surya_ocr"
    install_hint = "pip install surya-ocr"


class CalamariEngine(OptionalEngine):
    name = "calamari"
    command_name = "calamari-predict"
    install_hint = "pip install calamari-ocr"

    def available(self) -> bool:
        return super().available()
