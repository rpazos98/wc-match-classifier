from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _attack_scores() -> dict[str, float]:
    from db.query import team_attack_scores
    return team_attack_scores()


class GoalFestScorer(BaseScorer):
    name   = "Goal Fest"
    weight = 0.06

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.5, ""

        scores = _attack_scores()
        known  = [t for t in (home, away) if t != "TBD"]
        vals   = [scores[t] for t in known if t in scores]

        if not vals:
            return 0.5, ""

        raw = sum(vals) / len(vals)

        if raw >= 0.75:
            return raw, "Equipos con alto potencial ofensivo — partido con goles esperado"
        return raw, ""
