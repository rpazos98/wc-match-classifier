from functools import lru_cache
from . import BaseScorer, ScoringContext

_MAX_RANK_GAP = 40.0  # normalisation cap (ranks 1–48, typical spread ~40)


@lru_cache(maxsize=1)
def _ranks() -> dict[str, int]:
    from db.query import team_fifa_ranks
    return team_fifa_ranks()


class UpsetPotentialScorer(BaseScorer):
    name   = "Upset Potential"
    weight = 0.05

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        ranks  = _ranks()
        r_home = ranks.get(home)
        r_away = ranks.get(away)

        if r_home is None or r_away is None:
            return 0.0, ""

        gap = abs(r_home - r_away)
        raw = min(1.0, gap / _MAX_RANK_GAP)

        if raw >= 0.75:
            underdog = away if r_away > r_home else home
            favorite = home if r_away > r_home else away
            return raw, f"{underdog} como gran sorpresa frente a {favorite}"
        if raw >= 0.40:
            return raw, "Diferencia importante de jerarquía entre los equipos"
        return raw, ""
