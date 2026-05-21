"""
Upset Potential — narrative value of a possible upset.

Orthogonal to Competitive Tension: that scorer rewards balance (entropy),
this one rewards *imbalance* where the underdog has a realistic but
unlikely path to victory.

Formula:
  gap     = |elo_home - elo_away| normalised to [0, 1]
  threat  = p_underdog clamped to meaningful range
  upset_value = gap * threat * 4

Peaks when there's a clear favorite (high gap) but the underdog still
has ~20-30% chance (real threat). Falls off when:
  - Teams are equal (gap → 0, no "upset" narrative)
  - Mismatch is extreme (threat → 0, upset implausible)

Dark horse bonus adds narrative weight for tournament surprises.
"""
import math
from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _dark_horses() -> set[str]:
    from db.query import dark_horse_teams
    return dark_horse_teams()


class UpsetPotentialScorer(BaseScorer):
    name   = "Upset Potential"
    weight = 0.06

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        pred = ctx.prediction
        elo_gap = abs(pred.elo_home - pred.elo_away)
        # Normalise gap: 0 at equal, 1.0 at 400+ ELO difference
        gap = min(1.0, elo_gap / 400.0)

        p_under = pred.p_underdog
        # Threat: underdog's realistic chance, scaled so 0.30 → 1.0, 0.05 → 0.17
        threat = min(1.0, p_under / 0.30)

        # Upset value: high gap × real threat. Factor of 4 scales the product
        # so peak (gap=0.5, threat=1.0) → 1.0
        raw = min(1.0, gap * threat * 4.0)

        p_home = pred.p_home
        p_away = pred.p_away
        underdog = away if p_away < p_home else home
        favorite = home if p_away < p_home else away

        dh_boost = 0.15 if underdog in _dark_horses() else 0.0
        raw = min(1.0, raw + dh_boost)

        p_pct = f"{min(p_home, p_away):.0%}"
        if raw >= 0.70 and gap >= 0.3:
            dh = " (sorpresa del torneo)" if dh_boost else ""
            return raw, f"{underdog}{dh} con {p_pct} de chances contra {favorite}"
        if dh_boost:
            return raw, f"{underdog} es una sorpresa del torneo"
        return raw, ""
