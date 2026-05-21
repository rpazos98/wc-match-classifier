from functools import lru_cache
from . import BaseScorer, ScoringContext

# Players rated 86+ in FC26 are considered stars.
# Tier = (overall - 85) / 6   →   86→0.17  87→0.33  88→0.50  89→0.67  90→0.83  91→1.00
_STAR_THRESHOLD = 86
_TIER_BASE      = 85
_TIER_RANGE     = 6   # 91 - 85


@lru_cache(maxsize=1)
def _overall_map() -> dict[str, int]:
    from db.query import player_overall_ratings
    return player_overall_ratings()


def _best_star(players: tuple[str, ...]) -> tuple[float, list[str]]:
    """
    Return (best_tier 0.0–1.0, [star names sorted by tier]) for a squad.
    Only players rated >= _STAR_THRESHOLD count.
    """
    ratings = _overall_map()
    stars: list[tuple[str, float]] = []
    for player in players:
        overall = ratings.get(player)
        if overall is not None and overall >= _STAR_THRESHOLD:
            tier = (overall - _TIER_BASE) / _TIER_RANGE
            stars.append((player, tier))
    stars.sort(key=lambda x: x[1], reverse=True)
    best = stars[0][1] if stars else 0.0
    return best, [name for name, _ in stars]


class StarPowerScorer(BaseScorer):
    name   = "Star Power"
    weight = 0.05

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home_squad = ctx.match.home_squad
        away_squad = ctx.match.away_squad

        if not home_squad and not away_squad:
            return 0.5, ""  # abstain: no squad data

        star_home, home_stars = _best_star(home_squad.players) if home_squad else (0.0, [])
        star_away, away_stars = _best_star(away_squad.players) if away_squad else (0.0, [])

        if star_home == 0.0 and star_away == 0.0:
            return 0.0, ""

        # Average of both sides: naturally higher when BOTH teams bring stars.
        # Single 91-rated star  → (1.00 + 0) / 2 = 0.50
        # Dual 90-rated stars   → (0.75 + 0.75) / 2 = 0.75
        # 91-rated vs 90-rated  → (1.00 + 0.75) / 2 = 0.875
        raw = (star_home + star_away) / 2.0

        all_stars = home_stars + away_stars
        display   = all_stars[:3]
        suffix    = " y más" if len(all_stars) > 3 else ""
        reason    = ", ".join(display) + suffix + " en la cancha"

        return raw, reason
