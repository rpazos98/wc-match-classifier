from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _form_scores() -> dict[str, float]:
    from db.query import team_form_scores
    return team_form_scores()


class FormScorer(BaseScorer):
    name   = "Form"
    weight = 0.11

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.5, ""

        scores = _form_scores()
        known  = [t for t in (home, away) if t != "TBD"]
        vals   = [scores[t] for t in known if t in scores]

        if not vals:
            return 0.5, ""  # abstain: no form data

        raw = sum(vals) / len(vals)

        hot = [t for t in known if scores.get(t, 0) >= 0.75]
        if hot:
            names = " y ".join(hot)
            return raw, f"{names} en gran momento de forma"

        return raw, ""
