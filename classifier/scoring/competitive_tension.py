"""
Competitive Tension — evenly matched, high-quality teams.

Merges the former Suspense (pure entropy) and Expected Drama (entropy × prestige)
into a single orthogonal dimension: how tense will this match feel?

Formula:
  tension = entropy^0.7 * (0.4 + 0.6 * prestige) + vecer_bonus

- entropy^0.7: slightly compressed — even mid-entropy matches (0.6) still feel tense
- prestige floor of 0.4: a close match between weaker teams is still somewhat tense,
  but elite matchups get the full boost
- vecer_bonus: Vecer (2007) showed peak excitement occurs when the opponent is
  *slightly stronger* (p_underdog ≈ 0.35), not at perfect 50-50. A small bonus
  rewards this asymmetry — upset potential adds narrative tension.

This avoids the old double-counting where Suspense=entropy and
ExpectedDrama=entropy*prestige both rewarded the same signal.
"""
import math
from . import BaseScorer, ScoringContext

_MAX_ELO  = 2100.0
_BASE_ELO = 1400.0

# Vecer (2007): peak excitement at p_underdog ≈ 0.35 (slight favorite exists)
_VECER_PEAK  = 0.35
_VECER_WIDTH = 0.15
_VECER_MAX   = 0.08


class CompetitiveTensionScorer(BaseScorer):
    name   = "Competitive Tension"
    weight = 0.18
    literature = [
        "Vecer (2007) — excitement peaks with slight favorite, not 50-50",
        "Ely, Frankel & Kamenica (2015) — suspense = variance of beliefs",
        "Rottenberg (1956) — Uncertainty of Outcome Hypothesis",
        "Buraimo & Simmons (2015) — quality matters more than pure closeness",
    ]

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.5, ""

        pred     = ctx.prediction
        entropy  = pred.entropy
        avg_elo  = (pred.elo_home + pred.elo_away) / 2.0
        prestige = max(0.0, min(1.0, (avg_elo - _BASE_ELO) / (_MAX_ELO - _BASE_ELO)))

        base = (entropy ** 0.7) * (0.4 + 0.6 * prestige)

        # Vecer correction: slight asymmetry is more exciting than perfect balance
        p_under = pred.p_underdog
        vecer_bonus = max(0.0, 1.0 - abs(p_under - _VECER_PEAK) / _VECER_WIDTH) * _VECER_MAX

        raw = min(1.0, base + vecer_bonus)

        self._last = (entropy, prestige, avg_elo, pred, base, vecer_bonus)

        if raw >= 0.75:
            return raw, f"{home} vs {away} — duelo de élites completamente abierto"
        if raw >= 0.55:
            return raw, f"{home} vs {away} — partido equilibrado de buen nivel"
        if raw >= 0.40:
            return raw, f"{home} vs {away} — resultado incierto"
        return raw, ""

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if not hasattr(self, '_last'):
            return ""
        entropy, prestige, avg_elo, pred, base, vecer_bonus = self._last
        lines = (
            f"Probabilidades: {pred.p_home:.0%} / {pred.p_draw:.0%} / {pred.p_away:.0%}\n"
            f"Entropía Shannon normalizada = {entropy:.2f}\n"
            f"ELO promedio = {avg_elo:.0f} → prestigio = {prestige:.2f}\n"
            f"Base: entropy^0.7 × (0.4 + 0.6 × prestigio)\n"
            f"= {entropy:.2f}^0.7 × (0.4 + 0.6 × {prestige:.2f}) = {base:.2f}"
        )
        if vecer_bonus > 0.001:
            lines += (
                f"\nCorrección Vecer: p_underdog = {pred.p_underdog:.2f} → bonus = +{vecer_bonus:.3f}"
                f"\n(Vecer 2007: leve favorito → más potencial de sorpresa)"
            )
        lines += f"\nRaw final = {raw:.2f}"
        return lines
