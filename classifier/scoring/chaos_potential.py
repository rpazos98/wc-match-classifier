from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _attack_scores() -> dict[str, float]:
    from db.query import team_attack_scores
    return team_attack_scores()


@lru_cache(maxsize=1)
def _defense_scores() -> dict[str, float]:
    from db.query import team_defense_scores
    return team_defense_scores()


class ChaosPotentialScorer(BaseScorer):
    """
    Chaos Potential — open, high-scoring, unpredictable game likelihood.

    High when both teams attack aggressively AND defenses are fragile.
    Attack openness + defensive fragility + their synergy.
    """
    name   = "Chaos Potential"
    weight = 0.14

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        # Use predicted goals from simulation if available
        if ctx.predicted_home_goals is not None and ctx.predicted_away_goals is not None:
            total = ctx.predicted_home_goals + ctx.predicted_away_goals
            raw   = min(total / 5.0, 1.0)
            if total >= 5:
                return raw, f"Partido caótico predicho: {total} goles, juego completamente abierto"
            if total >= 3:
                return raw, f"Partido abierto: {total} goles predichos"
            if total >= 2:
                return raw, f"Partido con llegadas de ambos lados ({total} goles)"
            return raw, ""

        home = ctx.match.home
        away = ctx.match.away
        if home == "TBD" and away == "TBD":
            return 0.5, ""

        atk   = _attack_scores()
        dfn   = _defense_scores()
        known = [t for t in (home, away) if t != "TBD"]

        atk_vals = [atk[t] for t in known if t in atk]
        dfn_vals = [dfn[t] for t in known if t in dfn]

        if not atk_vals:
            return 0.5, ""

        avg_atk  = sum(atk_vals) / len(atk_vals)
        avg_dfn  = sum(dfn_vals) / len(dfn_vals) if dfn_vals else 0.5
        fragility = 1.0 - avg_dfn

        # Synergy: high attack + fragile defense = amplified chaos
        raw = min(1.0, (avg_atk * 2 + fragility + avg_atk * fragility) / 4.0)

        if raw >= 0.75:
            return raw, "Dos equipos con vocación ofensiva y defensas permeables — partido abierto"
        if raw >= 0.55:
            return raw, "Buen potencial ofensivo — se esperan llegadas"
        return raw, ""
