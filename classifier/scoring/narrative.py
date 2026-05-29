from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _wc_h2h_rivalry() -> dict[frozenset, float]:
    from db.query import wc_h2h_scores
    return wc_h2h_scores()


@lru_cache(maxsize=1)
def _wc_meetings() -> dict[frozenset, int]:
    from db.query import wc_h2h_meetings
    return wc_h2h_meetings()


@lru_cache(maxsize=1)
def _all_h2h() -> dict[frozenset, float]:
    from db.query import all_h2h_scores
    return all_h2h_scores()


@lru_cache(maxsize=1)
def _wc_drama() -> dict[frozenset, float]:
    from db.query import wc_drama_scores
    return wc_drama_scores()


class NarrativeScorer(BaseScorer):
    """
    Narrative — historical weight and story between two teams.

    Combines WC rivalry intensity, drama indicators, and all-competition
    history.  WC weight dominates because World Cup encounters are the
    most memorable; drama matters next (penalties, late goals, cards);
    general H2H is a minor enrichment.
    """
    name   = "Narrative"
    weight = 0.06
    literature = [
        "Tyler et al. (2024) — rivalry effects real but mixed; measurement methodology matters",
        "Nalbantis et al. (2017) — perceived competitiveness drives interest more than objective stats",
    ]

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" or away == "TBD":
            return 0.0, ""

        key      = frozenset({home, away})
        n_wc     = _wc_meetings().get(key, 0)
        rivalry  = _wc_h2h_rivalry().get(key, 0.0)
        all_h2h  = _all_h2h().get(key, 0.0)
        drama    = _wc_drama().get(key, 0.0)

        # WC rivalry dominates, drama next, general H2H minor enrichment
        raw = min(1.0, 0.55 * rivalry + 0.30 * drama + 0.15 * all_h2h)

        self._last = (n_wc, rivalry, all_h2h, drama)

        if raw < 0.10:
            return 0.0, ""

        if raw >= 0.70:
            label = "historic World Cup classic"
        elif raw >= 0.50:
            label = "historic rivalry"
        elif raw >= 0.25:
            label = "history in international football"
        else:
            label = "have met before"

        drama_note = ""
        if drama >= 0.7:
            drama_note = " — history of dramatic matches"
        elif drama >= 0.4:
            drama_note = " — intense encounters"

        if n_wc >= 3:
            return raw, f"{home} vs {away} — {label} ({n_wc} World Cup meetings){drama_note}"
        return raw, f"{home} vs {away} — {label}{drama_note}"

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if not hasattr(self, '_last'):
            return ""
        n_wc, rivalry, all_h2h, drama = self._last
        return (
            f"World Cup meetings = {n_wc}\n"
            f"WC rivalry = {rivalry:.2f}\n"
            f"Drama (goals, penalties, red cards) = {drama:.2f}\n"
            f"Total history (all competitions) = {all_h2h:.2f}\n"
            f"Formula: 0.55×WC + 0.30×drama + 0.15×history\n"
            f"= 0.55×{rivalry:.2f} + 0.30×{drama:.2f} + 0.15×{all_h2h:.2f} = {raw:.2f}\n"
            f"Conservative weight (6%) — Tyler et al. (2024): rivalry effect is real but inconsistent across contexts"
        )
