"""Comparação entre motores, sem votação cega nem texto inventado."""

from __future__ import annotations

from pathlib import Path

from .base import MotorIndisponivel, MotorPagina, RecognitionConfig, RecognitionEngine, ResultadoPagina


class EnsembleEngine(MotorPagina):
    """Executa vários motores e devolve o primário, registrando divergências."""

    name = "ensemble"

    def __init__(self, motores: list[RecognitionEngine]) -> None:
        if not motores:
            raise ValueError("Ensemble exige ao menos um motor.")
        self._motores = list(motores)

    def available(self) -> bool:
        return any(motor.available() for motor in self._motores)

    def recognize_page(
        self, image_path: Path | str, config: RecognitionConfig, numero_pagina: int = 1
    ) -> ResultadoPagina:
        resultados: list[ResultadoPagina] = []
        falhas: list[str] = []
        for motor in self._motores:
            if not motor.available():
                continue
            try:
                resultados.append(motor.recognize_page(image_path, config, numero_pagina))
            except MotorIndisponivel as erro:
                falhas.append(f"{motor.name}: {erro}")
        if not resultados:
            nomes = ", ".join(motor.name for motor in self._motores)
            detalhe = "; ".join(falhas)
            raise MotorIndisponivel(f"Nenhum motor do ensemble disponível ({nomes}). {detalhe}")
        primario = resultados[0]
        divergencias = tuple(
            f"{outro.motor}: texto diverge do primário ({primario.motor})"
            for outro in resultados[1:]
            if outro.texto_bruto.strip() != primario.texto_bruto.strip()
        )
        return ResultadoPagina(
            texto_bruto=primario.texto_bruto,
            linhas=primario.linhas,
            confianca_media=primario.confianca_media,
            motor=f"ensemble({primario.motor})",
            aviso=primario.aviso,
            divergencias=(*divergencias, *falhas),
        )
