"""
Competitive Tension — evenly matched, high-quality teams.

Merges the former Suspense (pure entropy) and Expected Drama (entropy × prestige)
into a single orthogonal dimension: how tense will this match feel?

Formula:
  tension = entropy^0.7 * (0.4 + 0.6 * prestige)

- entropy^0.7: slightly compressed — even mid-entropy matches (0.6) still feel tense
- prestige floor of 0.4: a close match between weaker teams is still somewhat tense,
  but elite matchups get the full boost

This avoids the old double-counting where Suspense=entropy and
ExpectedDrama=entropy*prestige both rewarded the same signal.
"""
import math
from . import BaseScorer, ScoringContext

_MAX_ELO  = 2100.0
_BASE_ELO = 1400.0


class CompetitiveTensionScorer(BaseScorer):
    name   = "Competitive Tension"
    weight = 0.18

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.5, ""

        pred     = ctx.prediction
        entropy  = pred.entropy
        avg_elo  = (pred.elo_home + pred.elo_away) / 2.0
        prestige = max(0.0, min(1.0, (avg_elo - _BASE_ELO) / (_MAX_ELO - _BASE_ELO)))

        raw = (entropy ** 0.7) * (0.4 + 0.6 * prestige)
        raw = min(1.0, raw)

        if raw >= 0.75:
            return raw, f"{home} vs {away} — duelo de élites completamente abierto"
        if raw >= 0.55:
            return raw, f"{home} vs {away} — partido equilibrado de buen nivel"
        if raw >= 0.40:
            return raw, f"{home} vs {away} — resultado incierto"
        return raw, ""
