from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _quality_scores() -> dict[str, float]:
    from db.query import team_quality_scores
    return team_quality_scores()


class MatchDramaScorer(BaseScorer):
    name   = "Match Drama"
    weight = 0.08

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.5, ""

        scores = _quality_scores()
        known  = [t for t in (home, away) if t != "TBD"]

        if len(known) < 2:
            return 0.5, ""

        q_home = scores.get(known[0], 0.5)
        q_away = scores.get(known[1], 0.5)

        # Closer quality → more likely to be a tight, dramatic match
        gap = abs(q_home - q_away)
        raw = 1.0 - gap

        if raw >= 0.85:
            return raw, f"{home} vs {away} — fuerzas muy parejas, partido cerrado esperado"
        if raw >= 0.70:
            return raw, f"{home} vs {away} — partido equilibrado"
        return raw, ""
