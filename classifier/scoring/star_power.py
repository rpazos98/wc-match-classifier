from functools import lru_cache
from . import BaseScorer, ScoringContext

# Players rated 86+ in FC26 are considered stars.
# Tier = (overall - 85) / 6   →   86→0.17  87→0.33  88→0.50  89→0.67  90→0.83  91→1.00
_STAR_THRESHOLD = 85
_TIER_BASE      = 84
_TIER_RANGE     = 7   # 91 - 84


@lru_cache(maxsize=1)
def _overall_map() -> dict[str, int]:
    from db.query import player_overall_ratings
    return player_overall_ratings()


def _star_score(players: tuple[str, ...]) -> tuple[float, float, list[str]]:
    """
    Return (depth_score 0.0–1.0, best_tier 0.0-1.0, [star names sorted by tier]).

    depth_score = weighted average of top 3 stars (1st=50%, 2nd=30%, 3rd=20%).
    This rewards squads with multiple stars over one-star teams.
    """
    ratings = _overall_map()
    stars: list[tuple[str, float]] = []
    for player in players:
        overall = ratings.get(player)
        if overall is not None and overall >= _STAR_THRESHOLD:
            tier = (overall - _TIER_BASE) / _TIER_RANGE
            stars.append((player, tier))
    stars.sort(key=lambda x: x[1], reverse=True)
    if not stars:
        return 0.0, 0.0, []

    best = stars[0][1]
    # Weighted average of top 3
    top3 = [t for _, t in stars[:3]]
    weights = [0.50, 0.30, 0.20]
    depth = sum(t * w for t, w in zip(top3, weights[:len(top3)]))
    # Normalize: if only 1 star, they get 50% of weight → scale up
    depth /= sum(weights[:len(top3)])

    return depth, best, [name for name, _ in stars]


# Stars rated 90+ are "elite" — dual-elite matchups get a narrative boost
_ELITE_THRESHOLD = 90
_ELITE_TIER      = (_ELITE_THRESHOLD - _TIER_BASE) / _TIER_RANGE  # 0.833


class StarPowerScorer(BaseScorer):
    name   = "Star Power"
    weight = 0.17
    literature = [
        "Buraimo & Simmons (2015) — star quality drives TV audiences more than outcome uncertainty",
        "Cox (2023) — team quality significant for UCL attendance, closeness is not",
    ]

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home_squad = ctx.match.home_squad
        away_squad = ctx.match.away_squad

        if not home_squad and not away_squad:
            return 0.5, ""  # abstain: no squad data

        depth_h, best_h, home_stars = _star_score(home_squad.players) if home_squad else (0.0, 0.0, [])
        depth_a, best_a, away_stars = _star_score(away_squad.players) if away_squad else (0.0, 0.0, [])

        if depth_h == 0.0 and depth_a == 0.0:
            return 0.0, ""

        # Average depth of both sides — rewards squads with multiple stars
        raw = (depth_h + depth_a) / 2.0

        # Dual-elite boost: when BOTH sides have 90+ best star, it's iconic
        both_elite = best_h >= _ELITE_TIER and best_a >= _ELITE_TIER
        if both_elite:
            raw = min(1.0, raw * 1.4)

        all_stars = home_stars + away_stars
        display   = all_stars[:4]
        suffix    = " y más" if len(all_stars) > 4 else ""

        if both_elite:
            reason = "Duelo de estrellas: " + " vs ".join(display[:2])
            if len(display) > 2:
                reason += " + " + ", ".join(display[2:]) + suffix
        else:
            reason = ", ".join(display) + suffix + " en la cancha"

        self._last = (depth_h, depth_a, best_h, best_a, both_elite, home_stars, away_stars)
        return raw, reason

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if not hasattr(self, '_last'):
            return ""
        depth_h, depth_a, best_h, best_a, both_elite, home_stars, away_stars = self._last
        ratings = _overall_map()
        lines = []
        home = ctx.match.home
        away = ctx.match.away
        for team, stars, depth in [(home, home_stars, depth_h), (away, away_stars, depth_a)]:
            top3 = stars[:3]
            if top3:
                descs = [f"{n} ({ratings.get(n, '?')})" for n in top3]
                lines.append(f"{team}: {', '.join(descs)} → profundidad = {depth:.2f}")
            else:
                lines.append(f"{team}: sin estrellas 85+")
        lines.append(f"Fórmula: (profundidad_local + profundidad_visitante) / 2")
        lines.append(f"= ({depth_h:.2f} + {depth_a:.2f}) / 2 = {(depth_h+depth_a)/2:.2f}")
        if both_elite:
            lines.append(f"Boost dual-elite (×1.4): ambos tienen 90+ OVR")
        lines.append(f"Raw final = {raw:.2f}")
        return "\n".join(lines)
