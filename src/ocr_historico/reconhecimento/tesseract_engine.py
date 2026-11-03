"""Motor Tesseract via subprocesso seguro, com TSV para confiança e caixas."""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
from pathlib import Path

from .base import LinhaRec, MotorIndisponivel, MotorPagina, RecognitionConfig, ResultadoPagina


def _parse_tsv(saida: str) -> tuple[str, list[LinhaRec], float | None]:
    leitor = csv.DictReader(io.StringIO(saida), delimiter="\t")
    linhas: list[LinhaRec] = []
    confiancas: list[float] = []
    for registro in leitor:
        try:
            if int(registro.get("level", "0")) != 5:
                continue
        except ValueError:
            continue
        texto = (registro.get("text") or "").strip()
        if not texto:
            continue
        try:
            conf_raw = float(registro.get("conf", "-1"))
        except ValueError:
            conf_raw = -1.0
        confianca = conf_raw / 100.0 if conf_raw >= 0 else None
        if confianca is not None:
            confiancas.append(confianca)
        linhas.append(
            LinhaRec(
                numero=len(linhas) + 1,
                x=int(float(registro.get("left", "0"))),
                y=int(float(registro.get("top", "0"))),
                largura=int(float(registro.get("width", "0"))),
                altura=int(float(registro.get("height", "0"))),
                texto=texto,
                confianca=confianca,
            )
        )
    bruto = "\n".join(linha.texto for linha in linhas)
    media = sum(confiancas) / len(confiancas) if confiancas else None
    return bruto, linhas, media


class TesseractEngine(MotorPagina):
    """Tesseract 5 para impressos e datilografados em português."""

    name = "tesseract"

    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def recognize_page(
        self,
        image_path: Path | str,
        config: RecognitionConfig,
        numero_pagina: int = 1,
    ) -> ResultadoPagina:
        if not self.available():
            raise MotorIndisponivel(
                "Tesseract não encontrado no PATH. Instale com 'sudo apt install tesseract-ocr tesseract-ocr-por'."
            )
        comando = [
            "tesseract",
            str(image_path),
            "stdout",
            "-l",
            config.idioma,
            "--oem",
            str(config.oem),
            "--psm",
            str(config.psm),
            "tsv",
        ]
        timeout = int(config.timeout_segundos or 300)
        try:
            processo = subprocess.run(comando, capture_output=True, text=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired as erro:
            raise MotorIndisponivel(f"Tesseract excedeu {timeout}s em {image_path}.") from erro
        except OSError as erro:
            raise MotorIndisponivel(f"Falha ao executar o Tesseract: {erro}") from erro
        if processo.returncode != 0:
            raise MotorIndisponivel(
                f"Tesseract retornou código {processo.returncode}: {(processo.stderr or '').strip()[:500]}"
            )
        bruto, linhas, media = _parse_tsv(processo.stdout)
        return ResultadoPagina(texto_bruto=bruto, linhas=tuple(linhas), confianca_media=media, motor=self.name)
