"""
Preference learning via Bayesian correlation weighting.

User rates historical matches 1–10.  For each scorer, compute Pearson r
between its raw values and user ratings.  Positive correlations → higher
weight.  Blend data-driven weights with DEFAULT_WEIGHTS using a confidence
ramp: at few ratings the prior dominates, at ~30+ the data takes over.

No decision trees, no forests — works well from 5 ratings onward.
"""
from __future__ import annotations

import numpy as np

from .models import Match, UserProfile

# Must match the scorers in build_default_engine() exactly.
SCORER_NAMES: list[str] = [
    "Favorite Team",
    "Competitive Tension",
    "Match Stage",
    "Star Power",
    "Chaos Potential",
    "Form",
    "Narrative",
    "Same Group",
]

DEFAULT_WEIGHTS: dict[str, float] = {
    "Favorite Team":        0.19,
    "Competitive Tension":  0.21,
    "Match Stage":          0.17,
    "Star Power":           0.14,
    "Chaos Potential":      0.12,
    "Form":                 0.08,
    "Narrative":            0.06,
    "Same Group":           0.03,
}

_RAMP_N = 30  # ratings needed for full data confidence


def rating_to_label(r: float) -> str:
    """Map a 1–10 mean rating to a category label."""
    if r >= 7.5:
        return "🔥 Imperdible"
    if r >= 4.5:
        return "👀 Tal Vez"
    return "📺 Resumen"


# ── Correlation-based weights ─────────────────────────────────────────────────

def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson r, 0.0 if constant or too few samples."""
    if len(x) < 3:
        return 0.0
    sx, sy = float(np.std(x)), float(np.std(y))
    if sx < 1e-9 or sy < 1e-9:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _correlation_weights(X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """
    Compute weights from Pearson r between each scorer and user ratings.
    Negative correlations → 0 (scorer hurts prediction, ignore it).
    """
    n_scorers = X.shape[1]
    raw = np.array([max(0.0, _pearson(X[:, i], y)) for i in range(n_scorers)])

    if raw.sum() < 1e-9:
        return {name: 1.0 / n_scorers for name in SCORER_NAMES}

    normed = raw / raw.sum()
    return {name: round(float(v), 4) for name, v in zip(SCORER_NAMES, normed)}


def _blend(
    prior: dict[str, float],
    data: dict[str, float],
    n_ratings: int,
) -> dict[str, float]:
    """
    Bayesian blend: (1 - α) * prior + α * data.
    α ramps linearly from 0 to 1 over _RAMP_N ratings.
    """
    alpha = min(1.0, n_ratings / _RAMP_N)
    blended = {}
    for name in SCORER_NAMES:
        p = prior.get(name, 0.0)
        d = data.get(name, 0.0)
        blended[name] = (1 - alpha) * p + alpha * d

    # Re-normalise to sum=1
    total = sum(blended.values())
    if total > 0:
        blended = {k: round(v / total, 4) for k, v in blended.items()}
    return blended


# ── Public API ────────────────────────────────────────────────────────────────

def fit_from_ratings(rated_examples: list[dict]) -> dict:
    """
    Learn weights from (raw_score_vector, rating 1–10) examples.

    rated_examples: list of {raw: {scorer_name: float}, rating: int}

    Returns:
      {weights, weight_delta, top_features, rating_stats, confidence}
    """
    n_scorers = len(SCORER_NAMES)

    if not rated_examples:
        return {
            "weights":      dict(DEFAULT_WEIGHTS),
            "weight_delta": {n: 0.0 for n in SCORER_NAMES},
            "top_features": [],
            "rating_stats": {},
            "confidence":   0.0,
        }

    X = np.array(
        [[ex["raw"].get(s, 0.5) for s in SCORER_NAMES] for ex in rated_examples],
        dtype=float,
    )
    y = np.array(
        [float(ex["rating"]) for ex in rated_examples],
        dtype=float,
    )

    data_weights = _correlation_weights(X, y)
    weights = _blend(DEFAULT_WEIGHTS, data_weights, len(y))

    top_features = sorted(
        [{"scorer": name, "importance": round(float(v), 4)}
         for name, v in weights.items()],
        key=lambda x: x["importance"],
        reverse=True,
    )

    rating_stats = {
        "mean": round(float(np.mean(y)), 1),
        "min":  int(np.min(y)),
        "max":  int(np.max(y)),
        "n":    len(y),
        "dist": {str(i): int((y == i).sum()) for i in range(1, 11) if (y == i).sum() > 0},
    }

    weight_delta = {
        name: round(float(weights[name]) - DEFAULT_WEIGHTS.get(name, 0.0), 4)
        for name in SCORER_NAMES
    }

    confidence = round(min(1.0, len(y) / _RAMP_N), 2)

    return {
        "weights":      weights,
        "weight_delta": weight_delta,
        "top_features": top_features[:6],
        "rating_stats": rating_stats,
        "confidence":   confidence,
    }
