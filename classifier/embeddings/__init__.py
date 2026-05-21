"""
Player embedding module.

Lazy singleton — index is built once on first access and cached.
"""
from __future__ import annotations

from functools import lru_cache

from .index import PlayerEmbeddingIndex


@lru_cache(maxsize=1)
def get_index() -> PlayerEmbeddingIndex:
    """Build and cache the player embedding index (runs once per process)."""
    return PlayerEmbeddingIndex.build()


__all__ = ["PlayerEmbeddingIndex", "get_index"]
