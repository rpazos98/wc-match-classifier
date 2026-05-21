from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _dark_horses() -> set[str]:
    from db.query import dark_horse_teams
    return dark_horse_teams()


class DarkHorseScorer(BaseScorer):
    name   = "Dark Horse"
    weight = 0.07

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.0, ""

        horses = _dark_horses()
        hits   = [t for t in (home, away) if t != "TBD" and t in horses]

        if not hits:
            return 0.0, ""

        raw   = 1.0 if len(hits) == 2 else 0.6
        names = " y ".join(hits)
        return raw, f"{names} como sorpresa del torneo"
