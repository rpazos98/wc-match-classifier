from . import BaseScorer, ScoringContext

_TIER_LABEL = {
    1.0:  "favorito",
    0.65: "te gusta",
    0.3:  "interesante",
}


def _affinity_label(aff: float) -> str:
    if aff >= 0.9:
        return "favorito"
    if aff >= 0.5:
        return "te gusta"
    return "interesante"


class FavoriteTeamScorer(BaseScorer):
    name   = "Favorite Team"
    weight = 0.19

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        affs  = ctx.profile.team_affinities
        home  = ctx.match.home.upper()
        away  = ctx.match.away.upper()

        if home == "TBD" or away == "TBD":
            return 0.0, ""

        aff_home = affs.get(home, 0.0)
        aff_away = affs.get(away, 0.0)

        if aff_home == 0.0 and aff_away == 0.0:
            return 0.0, ""

        hi = max(aff_home, aff_away)
        lo = min(aff_home, aff_away)

        # Both teams matter: the secondary adds up to 30% boost
        # ARG(S) vs BRA(A) = 1.0 + 0.3*0.65 = 1.195 → capped 1.0
        # ARG(S) vs nadie  = 1.0 + 0          = 1.0
        # MEX(A) vs CAN(B) = 0.65 + 0.3*0.30 = 0.74
        # MEX(A) vs nadie  = 0.65 + 0          = 0.65
        score = min(1.0, hi + 0.3 * lo)

        parts = []
        for code, aff in ((home, aff_home), (away, aff_away)):
            if aff > 0:
                parts.append(f"{code} ({_affinity_label(aff)})")
        reason = " vs ".join(parts) if len(parts) == 2 else f"{parts[0]} is playing"

        self._last = (aff_home, aff_away, hi, lo)
        return score, reason

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if not hasattr(self, '_last'):
            return ""
        aff_home, aff_away, hi, lo = self._last
        home = ctx.match.home
        away = ctx.match.away
        return (
            f"{home}: affinity = {aff_home:.2f}\n"
            f"{away}: affinity = {aff_away:.2f}\n"
            f"Formula: min(1.0, highest + 0.3 × lowest)\n"
            f"= min(1.0, {hi:.2f} + 0.3 × {lo:.2f}) = {raw:.2f}\n"
            f"Scale: S=1.0, A=0.65, B=0.30, no interest=0"
        )
