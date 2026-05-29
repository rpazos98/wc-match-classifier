from functools import lru_cache
from . import BaseScorer, ScoringContext
from ..models import Stage


def _affinity_label(aff: float) -> str:
    if aff >= 0.9:  return "favorito"
    if aff >= 0.5:  return "te gusta"
    return "casual"


@lru_cache(maxsize=1)
def _groups() -> dict[str, str]:
    """team_code → group_letter"""
    from db.query import team_group_map
    return team_group_map()


class SameGroupScorer(BaseScorer):
    name   = "Same Group"
    weight = 0.03

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        if ctx.match.stage != Stage.GROUP:
            return 0.0, ""

        home = ctx.match.home.upper()
        away = ctx.match.away.upper()
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        fav_affs = {t: a for t, a in ctx.profile.team_affinities.items() if a > 0}
        favs = set(fav_affs.keys())
        if not favs:
            return 0.0, ""

        groups     = _groups()
        fav_groups = {groups[f] for f in favs if f in groups}
        if not fav_groups:
            return 0.0, ""

        # Fav team is playing → direct stake, scaled by tier
        playing = [t for t in (home, away) if t in favs]
        if playing:
            best_aff = max(fav_affs[t] for t in playing)
            return best_aff, f"Your team's group match ({_affinity_label(best_aff)})"

        # Other teams in same group → affects standings, scaled by fav tier
        match_groups = {groups.get(home), groups.get(away)} - {None}
        shared = fav_groups & match_groups
        if shared:
            grp  = ", ".join(sorted(shared))
            fav  = next(f for f in favs if groups.get(f) in shared)
            aff  = fav_affs[fav]
            return 0.7 * aff, f"Group {grp} — affects {fav}'s standings"

        return 0.0, ""

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if ctx.match.stage != Stage.GROUP:
            return "Only applies in group stage"
        if raw > 0:
            return f"Scaled by team affinity → raw = {raw:.2f}"
        return "No teams of interest in this group → raw = 0.0"
