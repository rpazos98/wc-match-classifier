from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _conf_map() -> dict[str, str]:
    from db.query import confederation_map
    return confederation_map()


class ConfederationScorer(BaseScorer):
    name   = "Confederation"
    weight = 0.01

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        conf = _conf_map()
        fav_confs = {conf.get(t) for t, a in ctx.profile.team_affinities.items() if a > 0}
        fav_confs.discard(None)

        if not fav_confs:
            return 0.0, ""

        match_confs = {conf.get(t) for t in (home, away)}
        if match_confs & fav_confs:
            return 0.5, ""

        return 0.0, ""
