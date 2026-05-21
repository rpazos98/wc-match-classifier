"""
Cosine-similarity index over player feature vectors.

Usage:
    idx = PlayerEmbeddingIndex.build()
    matches = idx.similar_to("L. Messi", top_k=10, min_sim=0.90)
    # → [("T. Müller", 0.97), ("K. De Bruyne", 0.95), ...]
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


class PlayerEmbeddingIndex:
    def __init__(self, names: list[str], normed_matrix: np.ndarray) -> None:
        self._names = names
        self._name_idx: dict[str, int] = {n: i for i, n in enumerate(names)}
        # normed_matrix rows are already unit-normalized
        self._normed = normed_matrix  # shape (N, D)

    # ── Lookup ─────────────────────────────────────────────────────────────────

    def similar_to(
        self,
        name: str,
        top_k: int = 15,
        min_sim: float = 0.90,
    ) -> list[tuple[str, float]]:
        """
        Return up to top_k players most similar to `name` (excluding itself),
        filtered to cosine similarity >= min_sim.

        Returns empty list if `name` not in index.
        """
        idx = self._name_idx.get(name)
        if idx is None:
            return []

        sims: np.ndarray = self._normed @ self._normed[idx]  # (N,)
        sims[idx] = -1.0  # exclude self

        order = np.argsort(sims)[::-1]
        results: list[tuple[str, float]] = []
        for i in order[:top_k * 2]:  # oversample, then filter
            if float(sims[i]) < min_sim:
                break
            results.append((self._names[i], float(sims[i])))
            if len(results) >= top_k:
                break

        return results

    def best_match_in_squad(
        self,
        fav_name: str,
        squad_players: tuple[str, ...],
        min_sim: float = 0.88,
    ) -> tuple[str, float] | None:
        """
        Among `squad_players`, return the (player_name, similarity) most similar
        to `fav_name`, or None if no match above min_sim.
        """
        idx = self._name_idx.get(fav_name)
        if idx is None:
            return None

        fav_vec = self._normed[idx]

        best_name: str | None = None
        best_sim = min_sim - 1e-9  # must strictly exceed threshold

        for squad_player in squad_players:
            sidx = self._name_idx.get(squad_player)
            if sidx is None:
                continue
            sim = float(fav_vec @ self._normed[sidx])
            if sim > best_sim:
                best_sim = sim
                best_name = squad_player

        if best_name is None:
            return None
        return best_name, best_sim

    # ── Construction ───────────────────────────────────────────────────────────

    @classmethod
    def build(cls, csv_path: Path | None = None) -> "PlayerEmbeddingIndex":
        from .features import load_player_vectors

        if csv_path is None:
            csv_path = Path(__file__).parent.parent.parent / "data" / "FC26_20250921.csv"

        vectors = load_player_vectors(csv_path)
        if not vectors:
            raise ValueError(f"No player vectors loaded from {csv_path}")

        names = list(vectors.keys())
        matrix = np.stack([vectors[n] for n in names]).astype(np.float32)

        # Unit-normalize each row for cosine similarity via dot product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-8)
        normed = matrix / norms

        return cls(names, normed)

    def __len__(self) -> int:
        return len(self._names)

    def __contains__(self, name: str) -> bool:
        return name in self._name_idx
