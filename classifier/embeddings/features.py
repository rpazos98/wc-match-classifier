"""
Load FC26 player stats and produce normalized feature vectors.

Outfield players: 6 main attributes (pace, shooting, passing, dribbling, defending, physic).
Goalkeepers: 5 GK attributes (diving, handling, kicking, positioning, reflexes).

All raw stats are 1–99; we normalize to [0, 1] using fixed range [40, 99]
so the geometry reflects meaningful differences between real players.
"""
import csv
from pathlib import Path

import numpy as np

# Fixed normalization range: 40 = lowest realistic stat, 99 = max
_STAT_MIN = 40.0
_STAT_RANGE = 59.0  # 99 - 40

_OUTFIELD_COLS = ["pace", "shooting", "passing", "dribbling", "defending", "physic"]
_GK_COLS = [
    "goalkeeping_diving",
    "goalkeeping_handling",
    "goalkeeping_kicking",
    "goalkeeping_positioning",
    "goalkeeping_reflexes",
]

# Pad GK vectors with zeros for the outfield dims so all vectors have same length
# Layout: [pace, shooting, passing, dribbling, defending, physic, gk_diving, gk_handling,
#           gk_kicking, gk_positioning, gk_reflexes]
_DIM = len(_OUTFIELD_COLS) + len(_GK_COLS)  # 11


def _norm(val: str) -> float:
    try:
        v = float(val)
    except (ValueError, TypeError):
        return 0.0
    return max(0.0, min(1.0, (v - _STAT_MIN) / _STAT_RANGE))


def load_player_vectors(csv_path: Path) -> dict[str, np.ndarray]:
    """
    Returns {short_name: feature_vector} for all international-eligible players.
    Vectors are raw (not unit-normalized); normalization happens in the index.
    """
    vectors: dict[str, np.ndarray] = {}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only WC-squad-eligible (has national team assignment)
            if not row.get("nation_team_id", "").strip():
                continue

            name = row["short_name"].strip()
            if not name:
                continue

            is_gk = "GK" in row.get("player_positions", "")
            vec = np.zeros(_DIM, dtype=np.float32)

            if is_gk:
                for i, col in enumerate(_GK_COLS):
                    vec[len(_OUTFIELD_COLS) + i] = _norm(row.get(col, ""))
            else:
                for i, col in enumerate(_OUTFIELD_COLS):
                    vec[i] = _norm(row.get(col, ""))

            vectors[name] = vec

    return vectors
