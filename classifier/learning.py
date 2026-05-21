"""
Preference learning for scoring weight optimization.

Presents the user with pairwise match comparisons and learns optimal scorer
weights via logistic regression on the preference diffs.
"""
from __future__ import annotations

import random
import numpy as np

from .models import Match, UserProfile

SCORER_NAMES: list[str] = [
    "Favorite Team",
    "Time Availability",
    "Match Stage",
    "Form",
    "Favorite Player",
    "Match Drama",
    "Goal Fest",
    "Dark Horse",
    "Upset Potential",
    "Same Group",
    "Narrative Weight",
    "Team Strength",
    "Rivalry",
    "Confederation",
]

_STAGE_LABELS: dict[str, str] = {
    "group":       "Grupos",
    "r32":         "Ronda 32",
    "r16":         "Octavos",
    "qf":          "Cuartos",
    "sf":          "Semifinal",
    "third_place": "3er Lugar",
    "final":       "FINAL",
}


def _score_all(matches: list[Match], profile: UserProfile) -> dict:
    from . import build_default_engine
    engine = build_default_engine()
    return {m.match_id: engine.evaluate(m, profile) for m in matches}


def sample_pairs(
    matches: list[Match],
    profile: UserProfile,
    n: int = 12,
    seed: int | None = None,
) -> list[dict]:
    """
    Sample n pairs for preference elicitation.

    Strategy: 60% cross-tier (top vs bottom third by current score) for broad
    calibration, 40% adjacent-score pairs for fine-grained discrimination.
    A/B order is randomized to avoid position bias.
    """
    rng    = random.Random(seed)
    scored = sorted(matches, key=lambda m: _score_all(matches, profile)[m.match_id].total_score, reverse=True)

    # One evaluation pass is enough — reuse results
    results = _score_all(matches, profile)
    scored  = sorted(matches, key=lambda m: results[m.match_id].total_score, reverse=True)
    nm      = len(scored)

    pairs: list[tuple[Match, Match]] = []
    seen:  set[tuple[str, str]]      = set()

    n_cross = round(n * 0.6)
    top = scored[: nm // 3]
    bot = scored[2 * nm // 3 :]

    for _ in range(n_cross * 40):
        if len(pairs) >= n_cross:
            break
        a, b = rng.choice(top), rng.choice(bot)
        key  = tuple(sorted([a.match_id, b.match_id]))
        if key not in seen:
            seen.add(key)
            pairs.append((a, b))

    for _ in range((n - n_cross) * 40):
        if len(pairs) >= n:
            break
        i    = rng.randint(0, nm - 2)
        a, b = scored[i], scored[i + 1]
        key  = tuple(sorted([a.match_id, b.match_id]))
        if key not in seen:
            seen.add(key)
            pairs.append((a, b))

    rng.shuffle(pairs)

    def _info(m: Match) -> dict:
        r   = results[m.match_id]
        from zoneinfo import ZoneInfo
        tz  = profile.time_windows[0].timezone if profile.time_windows else ZoneInfo("UTC")
        loc = m.kickoff_utc.astimezone(tz)
        return {
            "match_id":      m.match_id,
            "home":          m.home,
            "away":          m.away,
            "stage":         m.stage.value,
            "stage_label":   _STAGE_LABELS.get(m.stage.value, m.stage.value),
            "kickoff_local": loc.strftime("%d/%m %H:%M"),
            "venue":         m.venue,
            "raw":           {k: round(v, 4) for k, v in r.raw_by_scorer.items()},
            "reasons":       r.reason_by_scorer,
        }

    out = []
    for a, b in pairs:
        if rng.random() < 0.5:
            a, b = b, a
        out.append({"match_a": _info(a), "match_b": _info(b)})
    return out


def fit_weights(preferences: list[dict]) -> dict[str, float]:
    """
    Logistic regression on preference diffs (no intercept, L2 regularized).

    Each preference: {'raw_a': dict[str,float], 'raw_b': dict[str,float],
                      'preferred': 'a'|'b'}

    Returns scorer_name → weight, normalized to sum 1.
    """
    if not preferences:
        u = 1.0 / len(SCORER_NAMES)
        return {name: u for name in SCORER_NAMES}

    X: list[np.ndarray] = []
    for pref in preferences:
        xa   = np.array([pref["raw_a"].get(s, 0.0) for s in SCORER_NAMES])
        xb   = np.array([pref["raw_b"].get(s, 0.0) for s in SCORER_NAMES])
        diff = xa - xb
        if pref["preferred"] == "b":
            diff = -diff
        X.append(diff)

    Xm  = np.array(X, dtype=float)       # (n_prefs, 9)
    w   = np.zeros(len(SCORER_NAMES))    # init at zero = uniform predictions

    lr  = 0.3
    lam = 0.05   # L2 — prevents collapse to a single feature

    for _ in range(3000):
        logits = np.clip(Xm @ w, -10.0, 10.0)
        probs  = 1.0 / (1.0 + np.exp(-logits))
        grad   = -(Xm.T @ (1.0 - probs)) / len(Xm) + lam * w
        w     -= lr * grad

    # Shift to strictly positive then normalize
    w = w - w.min() + 1e-3
    w = w / w.sum()

    return {name: round(float(v), 4) for name, v in zip(SCORER_NAMES, w)}
