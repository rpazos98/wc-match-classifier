from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _wc_h2h_rivalry() -> dict[frozenset, float]:
    from db.query import wc_h2h_scores
    return wc_h2h_scores()


@lru_cache(maxsize=1)
def _wc_meetings() -> dict[frozenset, int]:
    from db.query import wc_h2h_meetings
    return wc_h2h_meetings()


@lru_cache(maxsize=1)
def _all_h2h() -> dict[frozenset, float]:
    from db.query import all_h2h_scores
    return all_h2h_scores()


def _meetings_score(n: int) -> float:
    if n == 0:  return 0.0
    if n <= 2:  return 0.45
    if n <= 4:  return 0.65
    if n <= 6:  return 0.85
    return 1.0


class NarrativeScorer(BaseScorer):
    """
    Narrative — historical weight and story between two teams.

    Merges rivalry intensity (H2H quality at WC) and historical prestige
    (number of WC meetings) into a single storytelling score.
    WC history is primary; all-competition history enriches it.
    """
    name   = "Narrative"
    weight = 0.04

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        key      = frozenset({home, away})
        n_wc     = _wc_meetings().get(key, 0)
        rivalry  = _wc_h2h_rivalry().get(key, 0.0)
        all_h2h  = _all_h2h().get(key, 0.0)

        # WC-based: best of rivalry intensity and prestige from meetings
        wc_combined = max(rivalry, _meetings_score(n_wc))

        # All-competition enriches when WC data is sparse
        raw = min(1.0, 0.65 * wc_combined + 0.35 * all_h2h)

        if raw < 0.10:
            return 0.0, ""

        if raw >= 0.85:
            label = "clásico histórico del Mundial"
        elif raw >= 0.60:
            label = "rivalidad histórica"
        elif raw >= 0.30:
            label = "historia en el fútbol internacional"
        else:
            label = "se han enfrentado antes"

        if n_wc >= 3:
            return raw, f"{home} vs {away} — {label} ({n_wc} duelos en el Mundial)"
        return raw, f"{home} vs {away} — {label}"
