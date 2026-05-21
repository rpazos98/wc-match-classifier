from functools import lru_cache
from . import BaseScorer, ScoringContext
from ..models import Stage


@lru_cache(maxsize=1)
def _groups() -> dict[str, str]:
    """team_code → group_letter"""
    from db.query import team_group_map
    return team_group_map()


class SameGroupScorer(BaseScorer):
    name   = "Same Group"
    weight = 0.04

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        if ctx.match.stage != Stage.GROUP:
            return 0.0, ""

        home = ctx.match.home.upper()
        away = ctx.match.away.upper()
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        favs = {t.upper() for t in ctx.profile.favorite_teams}
        if not favs:
            return 0.0, ""

        groups     = _groups()
        fav_groups = {groups[f] for f in favs if f in groups}
        if not fav_groups:
            return 0.0, ""

        # Fav team is playing → direct stake in this match
        if home in favs or away in favs:
            return 1.0, f"Partido del grupo de tu equipo favorito"

        # Other teams in same group → affects standings
        match_groups = {groups.get(home), groups.get(away)} - {None}
        shared = fav_groups & match_groups
        if shared:
            grp  = ", ".join(sorted(shared))
            fav  = next(f for f in favs if groups.get(f) in shared)
            return 0.7, f"Grupo {grp} — afecta la tabla de {fav}"

        return 0.0, ""
