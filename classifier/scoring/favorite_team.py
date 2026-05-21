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

        score = max(aff_home, aff_away)

        # Build reason from the higher-affinity team(s)
        parts = []
        for code, aff in ((home, aff_home), (away, aff_away)):
            if aff > 0:
                parts.append(f"{code} ({_affinity_label(aff)})")
        reason = " vs ".join(parts) if len(parts) == 2 else f"{parts[0]} está jugando"

        return score, reason
