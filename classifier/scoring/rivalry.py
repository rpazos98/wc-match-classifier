from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _wc_scores() -> dict[frozenset, float]:
    from db.query import wc_h2h_scores
    return wc_h2h_scores()


@lru_cache(maxsize=1)
def _all_scores() -> dict[frozenset, float]:
    from db.query import all_h2h_scores
    return all_h2h_scores()


class RivalryScorer(BaseScorer):
    name   = "Rivalry"
    weight = 0.01

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        key = frozenset({home, away})
        wc  = _wc_scores().get(key)
        if wc is not None and wc >= 0.1:
            return wc, f"{home} vs {away} — {_rivalry_label(wc)} en la Copa del Mundo"

        # Fallback: all-competition H2H with 0.6 discount
        allh2h = _all_scores().get(key)
        if allh2h is not None:
            score = allh2h * 0.6
            if score >= 0.1:
                return score, f"{home} vs {away} — {_rivalry_label(score)} en el fútbol internacional"

        return 0.0, ""


def _rivalry_label(score: float) -> str:
    if score >= 0.8:
        return "clásico histórico"
    if score >= 0.5:
        return "rivalidad histórica"
    return "se han enfrentado antes"
