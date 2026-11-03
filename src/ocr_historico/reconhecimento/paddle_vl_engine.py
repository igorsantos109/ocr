"""Compat: paddlevl removido — use qwen3_vl. Mantido como alias."""
from .qwen3vl_engine import Qwen3VLEngine as PaddleVLEngine  # noqa: F401

# Re-export para compatibilidade
__all__ = ["PaddleVLEngine"]
