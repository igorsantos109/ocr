"""Ingestão local: descoberta, hash, PDF e imagens (Marco 1)."""

from .arquivos import ArquivoDescoberto, descobrir_arquivos
from .hash import calcular_sha256
from .inventario import Inventario, ItemInventario, inventariar_entrada, salvar_inventario
from .preservacao import ArtefatoPreservado, preservar_original
from .servico import ResumoIngestao, ingerir_entrada

__all__ = [
    "ArtefatoPreservado",
    "ArquivoDescoberto",
    "Inventario",
    "ItemInventario",
    "ResumoIngestao",
    "calcular_sha256",
    "descobrir_arquivos",
    "ingerir_entrada",
    "inventariar_entrada",
    "preservar_original",
    "salvar_inventario",
]
