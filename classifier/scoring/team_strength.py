from functools import lru_cache
from . import BaseScorer, ScoringContext

_ELITE_THRESHOLD = 0.75   # quality_score for top-tier teams


@lru_cache(maxsize=1)
def _quality_scores() -> dict[str, float]:
    from db.query import team_quality_scores
    return team_quality_scores()


@lru_cache(maxsize=1)
def _dark_horses() -> set[str]:
    from db.query import dark_horse_teams
    return dark_horse_teams()


class TeamStrengthScorer(BaseScorer):
    name   = "Team Strength"
    weight = 0.03

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.5, ""

        scores_map = _quality_scores()
        horses     = _dark_horses()
        known      = [t for t in (home, away) if t != "TBD"]

        vals = [scores_map.get(t, 0.5) for t in known]
        elite_score = sum(vals) / len(vals)

        # Upset potential: high when a dark horse faces an elite team
        has_elite   = any(scores_map.get(t, 0) >= _ELITE_THRESHOLD for t in known)
        has_horse   = any(t in horses for t in known)
        upset_score = 1.0 if (has_elite and has_horse) else 0.0

        raw = 0.7 * elite_score + 0.3 * upset_score

        if all(scores_map.get(t, 0.5) == 0.5 for t in known):
            return raw, ""

        parts = [f"{t} ({scores_map.get(t, 0.5):.0%})" for t in known]
        return raw, "Calidad de equipos: " + ", ".join(parts)
