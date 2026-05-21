from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _rivals() -> dict[str, set[str]]:
    from db.query import wc_rivals
    return wc_rivals()


class FavoriteTeamScorer(BaseScorer):
    name   = "Favorite Team"
    weight = 0.28

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        favs = {t.upper() for t in ctx.profile.favorite_teams}
        home = ctx.match.home.upper()
        away = ctx.match.away.upper()
        hits = [t for t in (home, away) if t in favs and t != "TBD"]

        if hits:
            names = " y ".join(hits)
            return 1.0, f"{names} (tu equipo favorito) está jugando"

        # Rival partial credit
        rivals_map = _rivals()
        rival_hits = [
            t for t in (home, away)
            if t != "TBD" and any(t in rivals_map.get(fav, set()) for fav in favs)
        ]
        if rival_hits:
            names = " y ".join(rival_hits)
            return 0.35, f"{names} — rival histórico de tu equipo favorito"

        return 0.0, ""
