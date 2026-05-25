"""
Preference learning via Ridge regression with interaction features.

User rates historical matches 1–10.  We fit a Ridge regression on raw scorer
values plus pairwise interaction terms (raw_i × raw_j).  Positive coefficients
→ higher weight.  Blend data-driven weights with DEFAULT_WEIGHTS using a
confidence ramp: at few ratings the prior dominates, at ~20+ the data takes over.

Active learning: when selecting calibration matches, pick those where the
current model is most uncertain (highest prediction variance via bootstrap).
"""
from __future__ import annotations

from itertools import combinations

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

# Key interaction pairs — discovered combos that matter
INTERACTION_PAIRS: list[tuple[str, str]] = [
    ("Favorite Team", "Match Stage"),       # your team in a big match
    ("Competitive Tension", "Star Power"),   # close game between stars
    ("Chaos Potential", "Match Stage"),      # chaos in knockout = drama
    ("Competitive Tension", "Narrative"),    # rivalry + close = electric
    ("Favorite Team", "Star Power"),         # your team has stars
    ("Chaos Potential", "Narrative"),        # chaotic rivalry
    ("Competitive Tension", "Chaos Potential"),  # Vecer (2007): close + high-scoring = excitement
]

INTERACTION_NAMES: list[str] = [f"{a} × {b}" for a, b in INTERACTION_PAIRS]

DEFAULT_WEIGHTS: dict[str, float] = {
    "Favorite Team":        0.19,
    "Competitive Tension":  0.18,
    "Match Stage":          0.17,
    "Star Power":           0.17,
    "Chaos Potential":      0.12,
    "Form":                 0.08,
    "Narrative":            0.06,
    "Same Group":           0.03,
}

_RAMP_N = 20  # ratings needed for full data confidence (down from 30 — Ridge needs less)


def rating_to_label(r: float) -> str:
    """Map a 1–10 mean rating to a category label."""
    if r >= 7.5:
        return "🔥 Imperdible"
    if r >= 4.5:
        return "👀 Tal Vez"
    return "📺 Resumen"


# ── Feature matrix construction ──────────────────────────────────────────────

def _build_feature_matrix(
    raw_examples: list[dict],
) -> tuple[np.ndarray, list[str]]:
    """
    Build feature matrix with base scorers + interaction terms.
    Returns (X, feature_names).
    """
    n = len(raw_examples)
    n_base = len(SCORER_NAMES)
    n_interact = len(INTERACTION_PAIRS)
    feature_names = list(SCORER_NAMES) + list(INTERACTION_NAMES)

    X = np.zeros((n, n_base + n_interact), dtype=float)

    for i, ex in enumerate(raw_examples):
        raw = ex["raw"]
        # Base features
        for j, s in enumerate(SCORER_NAMES):
            X[i, j] = raw.get(s, 0.5)
        # Interaction features
        for k, (a, b) in enumerate(INTERACTION_PAIRS):
            X[i, n_base + k] = raw.get(a, 0.5) * raw.get(b, 0.5)

    return X, feature_names


def _build_single_vector(raw: dict[str, float]) -> np.ndarray:
    """Build feature vector for a single match (for prediction/uncertainty)."""
    n_base = len(SCORER_NAMES)
    n_interact = len(INTERACTION_PAIRS)
    vec = np.zeros(n_base + n_interact, dtype=float)

    for j, s in enumerate(SCORER_NAMES):
        vec[j] = raw.get(s, 0.5)
    for k, (a, b) in enumerate(INTERACTION_PAIRS):
        vec[n_base + k] = raw.get(a, 0.5) * raw.get(b, 0.5)

    return vec


# ── Ridge regression weights ────────────────────────────────────────────────

def _ridge_weights(X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """
    Fit Ridge regression, extract base-scorer weights from coefficients.
    Interaction coefficients are folded into the model but reported separately.
    """
    from sklearn.linear_model import Ridge

    model = Ridge(alpha=1.0, fit_intercept=True)
    model.fit(X, y)

    coefs = model.coef_
    n_base = len(SCORER_NAMES)

    # Base scorer weights: use abs(coef) as importance, then normalise
    base_coefs = coefs[:n_base]
    importance = np.array([max(0.0, c) for c in base_coefs])

    if importance.sum() < 1e-9:
        return {name: 1.0 / n_base for name in SCORER_NAMES}

    normed = importance / importance.sum()
    return {name: round(float(v), 4) for name, v in zip(SCORER_NAMES, normed)}


def _ridge_full(X: np.ndarray, y: np.ndarray) -> tuple[dict[str, float], dict[str, float], "Ridge"]:
    """
    Full Ridge fit returning base weights, interaction strengths, and the model.
    """
    from sklearn.linear_model import Ridge

    model = Ridge(alpha=1.0, fit_intercept=True)
    model.fit(X, y)

    coefs = model.coef_
    n_base = len(SCORER_NAMES)

    # Base weights
    base_coefs = coefs[:n_base]
    importance = np.array([max(0.0, c) for c in base_coefs])
    if importance.sum() < 1e-9:
        base_weights = {name: 1.0 / n_base for name in SCORER_NAMES}
    else:
        normed = importance / importance.sum()
        base_weights = {name: round(float(v), 4) for name, v in zip(SCORER_NAMES, normed)}

    # Interaction strengths (raw coefficients, not normalised)
    interact_coefs = coefs[n_base:]
    interactions = {
        name: round(float(c), 4)
        for name, c in zip(INTERACTION_NAMES, interact_coefs)
    }

    return base_weights, interactions, model


# ── Bayesian blend ──────────────────────────────────────────────────────────

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

    total = sum(blended.values())
    if total > 0:
        blended = {k: round(v / total, 4) for k, v in blended.items()}
    return blended


# ── Active learning: uncertainty estimation ─────────────────────────────────

def predict_uncertainty(
    rated_examples: list[dict],
    candidate_raws: list[dict[str, float]],
    n_bootstrap: int = 50,
) -> list[float]:
    """
    Estimate prediction uncertainty for candidate matches using bootstrap.

    Fits n_bootstrap Ridge models on resampled training data, predicts each
    candidate, returns std of predictions as uncertainty measure.

    Higher uncertainty = model disagrees across bootstraps = more informative
    to rate this match next.
    """
    if len(rated_examples) < 5:
        # Not enough data — return uniform uncertainty (feature spread as proxy)
        uncertainties = []
        for raw in candidate_raws:
            vec = _build_single_vector(raw)
            spread = float(np.std(vec))
            uncertainties.append(spread)
        return uncertainties

    X_train, _ = _build_feature_matrix(rated_examples)
    y_train = np.array([float(ex["rating"]) for ex in rated_examples])

    X_cand = np.array([_build_single_vector(raw) for raw in candidate_raws])

    from sklearn.linear_model import Ridge

    rng = np.random.RandomState(42)
    predictions = np.zeros((n_bootstrap, len(candidate_raws)))

    for b in range(n_bootstrap):
        idx = rng.choice(len(y_train), size=len(y_train), replace=True)
        model = Ridge(alpha=1.0, fit_intercept=True)
        model.fit(X_train[idx], y_train[idx])
        predictions[b] = model.predict(X_cand)

    return [float(v) for v in np.std(predictions, axis=0)]


# ── Public API ────────────────────────────────────────────────────────────────

def fit_from_ratings(rated_examples: list[dict]) -> dict:
    """
    Learn weights from (raw_score_vector, rating 1–10) examples.

    Uses Ridge regression with interaction features when enough data exists,
    falls back to Pearson correlation for < 5 examples.

    Returns:
      {weights, weight_delta, top_features, interactions, rating_stats, confidence, method}
    """
    if not rated_examples:
        return {
            "weights":      dict(DEFAULT_WEIGHTS),
            "weight_delta": {n: 0.0 for n in SCORER_NAMES},
            "top_features": [],
            "interactions": {},
            "rating_stats": {},
            "confidence":   0.0,
            "method":       "prior",
        }

    X, feature_names = _build_feature_matrix(rated_examples)
    y = np.array([float(ex["rating"]) for ex in rated_examples], dtype=float)

    n_samples = len(y)

    if n_samples < 5:
        # Too few for Ridge — use simple Pearson on base features only
        data_weights = _pearson_weights(X[:, :len(SCORER_NAMES)], y)
        weights = _blend(DEFAULT_WEIGHTS, data_weights, n_samples)
        interactions = {}
        method = "pearson"
    else:
        data_weights, interactions, model = _ridge_full(X, y)
        weights = _blend(DEFAULT_WEIGHTS, data_weights, n_samples)
        method = "ridge"

    top_features = sorted(
        [{"scorer": name, "importance": round(float(v), 4)}
         for name, v in weights.items()],
        key=lambda x: x["importance"],
        reverse=True,
    )

    # Top interactions (only significant ones)
    top_interactions = {
        k: v for k, v in sorted(interactions.items(), key=lambda x: abs(x[1]), reverse=True)
        if abs(v) > 0.1
    }

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
        "interactions": top_interactions,
        "rating_stats": rating_stats,
        "confidence":   confidence,
        "method":       method,
    }


# ── Fallback: Pearson for < 5 samples ───────────────────────────────────────

def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return 0.0
    sx, sy = float(np.std(x)), float(np.std(y))
    if sx < 1e-9 or sy < 1e-9:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _pearson_weights(X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    n_scorers = X.shape[1]
    raw = np.array([max(0.0, _pearson(X[:, i], y)) for i in range(n_scorers)])
    if raw.sum() < 1e-9:
        return {name: 1.0 / n_scorers for name in SCORER_NAMES}
    normed = raw / raw.sum()
    return {name: round(float(v), 4) for name, v in zip(SCORER_NAMES, normed)}