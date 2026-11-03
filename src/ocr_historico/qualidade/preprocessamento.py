"""Pré-processamento puro e testável, guiado pelo YAML de cada perfil.

Sequência: tons de cinza → redução de ruído → deskew → CLAHE →
correção de fundo → upscale → binarização adaptativa (opcional).
Sem OpenCV, cada etapa devolve a imagem inalterada com aviso.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

try:
    import cv2
    import numpy as np

    _TEM_CV2 = True
except ImportError:  # pragma: no cover - ambiente sem OpenCV
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _TEM_CV2 = False


def tem_opencv() -> bool:
    return _TEM_CV2


def ler_cinza(caminho: Path | str):
    """Lê uma imagem em tons de cinza como matriz 2D."""
    with Image.open(caminho) as img:
        cinza = img.convert("L")
        if _TEM_CV2:
            return np.array(cinza)
        return cinza


def para_cinza(imagem):
    if _TEM_CV2:
        if len(np.shape(imagem)) == 2:
            return imagem
        return cv2.cvtColor(imagem, cv2.COLOR_RGB2GRAY)
    return imagem.convert("L") if isinstance(imagem, Image.Image) else imagem


def reduzir_ruido(imagem, nivel: str = "leve"):
    if not _TEM_CV2 or nivel in {"nenhum", "none", ""}:
        return imagem
    força = 3 if nivel == "leve" else 5
    return cv2.medianBlur(imagem, força)


def corrigir_inclinacao(imagem) -> tuple[Any, float]:
    """Estima e desfaz a inclinação; devolve (imagem, ângulo em graus)."""
    if not _TEM_CV2:
        return imagem, 0.0
    _, binaria = cv2.threshold(imagem, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pontos = np.column_stack(np.where(binaria < 128))
    if len(pontos) < 10:
        return imagem, 0.0
    angulo = cv2.minAreaRect(pontos)[-1]
    angulo = angulo + 90.0 if angulo < -45.0 else angulo
    if abs(angulo) < 0.1:
        return imagem, 0.0
    centro = (imagem.shape[1] / 2.0, imagem.shape[0] / 2.0)
    matriz = cv2.getRotationMatrix2D(centro, angulo, 1.0)
    girada = cv2.warpAffine(imagem, matriz, (imagem.shape[1], imagem.shape[0]), borderValue=255)
    return girada, round(float(angulo), 2)


def realce_clahe(imagem):
    if not _TEM_CV2:
        return imagem
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(imagem)


def corrigir_fundo(imagem):
    """Normaliza iluminação irregular dividindo pelo fundo estimado."""
    if not _TEM_CV2:
        return imagem
    fundo = cv2.medianBlur(imagem, 51)
    fundo = np.maximum(fundo, 1)
    normalizada = np.clip(imagem.astype(float) / fundo.astype(float) * 255.0, 0, 255)
    return normalizada.astype(np.uint8)


def ampliar(imagem, fator: float):
    if fator == 1.0:
        return imagem
    if _TEM_CV2:
        nova = (round(imagem.shape[1] * fator), round(imagem.shape[0] * fator))
        return cv2.resize(imagem, nova, interpolation=cv2.INTER_CUBIC)
    largura, altura = imagem.size
    return imagem.resize((round(largura * fator), round(altura * fator)), Image.Resampling.BICUBIC)


def binarizar(imagem):
    if not _TEM_CV2:
        return imagem
    _, saida = cv2.threshold(imagem, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return saida


def _salvar(imagem, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if _TEM_CV2 and not isinstance(imagem, Image.Image):
        Image.fromarray(imagem).save(destino)
    else:
        imagem.save(destino)


def aplicar_pipeline(caminho: Path | str, destino: Path, pre: Any) -> dict[str, Any]:
    """Aplica a sequência do perfil e salva a derivada em `destino`.

    `pre` é o bloco `preprocessamento` da configuração. Devolve as etapas
    aplicadas e o ângulo de deskew, para auditoria.
    """
    etapas: list[str] = []
    avisos: list[str] = []
    if not _TEM_CV2:
        avisos.append("OpenCV ausente; imagem enviada ao OCR sem pré-processamento.")
    imagem = ler_cinza(caminho)
    metricas_antes = None
    try:
        from .metricas import avaliar_imagem

        metricas_antes = avaliar_imagem(caminho).to_dict()
    except (OSError, ValueError):
        avisos.append("Não foi possível calcular métricas antes do pré-processamento.")
    etapas.append("grayscale")
    if getattr(pre, "denoise", "leve") not in {"nenhum", "none", ""}:
        imagem = reduzir_ruido(imagem, str(getattr(pre, "denoise", "leve")))
        etapas.append("denoise")
    angulo = 0.0
    if bool(getattr(pre, "deskew", True)):
        imagem, angulo = corrigir_inclinacao(imagem)
        etapas.append("deskew")
    if bool(getattr(pre, "clahe", False)):
        imagem = realce_clahe(imagem)
        etapas.append("clahe")
    if bool(getattr(pre, "remover_fundo", False)):
        imagem = corrigir_fundo(imagem)
        etapas.append("remover_fundo")
    fator = float(getattr(pre, "upscale", 1.0))
    if fator != 1.0:
        imagem = ampliar(imagem, fator)
        etapas.append(f"upscale:{fator}")
    if bool(getattr(pre, "binarizacao", False)):
        imagem = binarizar(imagem)
        etapas.append("binarizacao")
    _salvar(imagem, destino)
    metricas_depois = None
    try:
        from .metricas import avaliar_imagem

        metricas_depois = avaliar_imagem(destino).to_dict()
    except (OSError, ValueError):
        avisos.append("Não foi possível calcular métricas depois do pré-processamento.")
    return {
        "etapas": etapas,
        "angulo_deskew": angulo,
        "avisos": avisos,
        "metricas_antes": metricas_antes,
        "metricas_depois": metricas_depois,
    }
