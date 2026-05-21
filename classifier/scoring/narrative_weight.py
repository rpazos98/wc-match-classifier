from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _meetings() -> dict[frozenset, int]:
    from db.query import wc_h2h_meetings
    return wc_h2h_meetings()


def _meetings_to_raw(n: int) -> float:
    if n == 0:  return 0.4   # primera vez en la historia del Mundial
    if n <= 2:  return 0.55
    if n <= 4:  return 0.70
    if n <= 6:  return 0.85
    return 1.0               # fixture legendario


class NarrativeWeightScorer(BaseScorer):
    name   = "Narrative Weight"
    weight = 0.04

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        n   = _meetings().get(frozenset({home, away}), 0)
        raw = _meetings_to_raw(n)

        if n == 0:
            return raw, f"{home} vs {away} — primera vez que se enfrentan en un Mundial"
        if n >= 5:
            return raw, f"{home} vs {away} — {n} duelos en la historia del Mundial"
        return raw, ""
