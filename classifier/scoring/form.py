from . import BaseScorer, ScoringContext


class FormScorer(BaseScorer):
    """
    Form / Momentum — teams trending upward based on ELO trajectory.

    Measures ELO change over the last 8 matches for each team.
    form_delta in [-1, 1]; mapped to [0, 1] then weighted toward hotter team.
    """
    name   = "Form"
    weight = 0.06

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.5, ""

        from classifier.elo import form_delta
        known = [t for t in (home, away) if t != "TBD"]
        if not known:
            return 0.5, ""

        # form_delta in [-1, 1] → normalise to [0, 1]
        deltas = {t: (form_delta(t) + 1.0) / 2.0 for t in known}
        vals   = list(deltas.values())

        # Weight toward hotter team: (sum + max) / (n + 1)
        raw = (sum(vals) + max(vals)) / (len(vals) + 1)

        hot = [t for t, v in deltas.items() if v >= 0.65]
        if hot:
            names = " y ".join(hot)
            return raw, f"{names} en gran momento de forma"
        return raw, ""
