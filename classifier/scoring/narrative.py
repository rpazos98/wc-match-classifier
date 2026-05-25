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
            label = "clásico histórico del Mundial"
        elif raw >= 0.50:
            label = "rivalidad histórica"
        elif raw >= 0.25:
            label = "historia en el fútbol internacional"
        else:
            label = "se han enfrentado antes"

        drama_note = ""
        if drama >= 0.7:
            drama_note = " — historial de partidos dramáticos"
        elif drama >= 0.4:
            drama_note = " — encuentros intensos"

        if n_wc >= 3:
            return raw, f"{home} vs {away} — {label} ({n_wc} duelos en el Mundial){drama_note}"
        return raw, f"{home} vs {away} — {label}{drama_note}"

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if not hasattr(self, '_last'):
            return ""
        n_wc, rivalry, all_h2h, drama = self._last
        return (
            f"Duelos mundialistas = {n_wc}\n"
            f"Rivalidad WC = {rivalry:.2f}\n"
            f"Drama (goles, penales, rojas) = {drama:.2f}\n"
            f"Historial total (todas las competiciones) = {all_h2h:.2f}\n"
            f"Fórmula: 0.55×WC + 0.30×drama + 0.15×historial\n"
            f"= 0.55×{rivalry:.2f} + 0.30×{drama:.2f} + 0.15×{all_h2h:.2f} = {raw:.2f}\n"
            f"Peso conservador (6%) — Tyler et al. (2024): efecto rivalidad es real pero inconsistente entre contextos"
        )
