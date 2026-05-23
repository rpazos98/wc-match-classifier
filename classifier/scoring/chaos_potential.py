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
    weight = 0.12

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        # Use predicted goals from simulation if available
        if ctx.predicted_home_goals is not None and ctx.predicted_away_goals is not None:
            total = ctx.predicted_home_goals + ctx.predicted_away_goals
            raw   = min(total / 5.0, 1.0)
            hg_r = round(ctx.predicted_home_goals, 1)
            ag_r = round(ctx.predicted_away_goals, 1)
            total_r = round(total, 1)
            score_str = f"promedio {hg_r}-{ag_r} ({total_r} goles/partido)"
            if total >= 4.5:
                return raw, f"Partido caótico: {score_str}"
            if total >= 3:
                return raw, f"Partido abierto: {score_str}"
            if total >= 2:
                return raw, f"Llegadas de ambos lados: {score_str}"
            return raw, f"Partido cerrado: {score_str}"

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

        self._last_stats = (avg_atk, avg_dfn, fragility)

        if raw >= 0.75:
            return raw, "Dos equipos con vocación ofensiva y defensas permeables — partido abierto"
        if raw >= 0.55:
            return raw, "Buen potencial ofensivo — se esperan llegadas"
        return raw, ""

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        if ctx.predicted_home_goals is not None and ctx.predicted_away_goals is not None:
            hg = ctx.predicted_home_goals
            ag = ctx.predicted_away_goals
            total = hg + ag
            return (
                f"Goles promedio por simulación: {hg:.1f} - {ag:.1f}\n"
                f"Total = {total:.1f}\n"
                f"Fórmula: min(total / 5.0, 1.0)\n"
                f"= min({total:.1f} / 5.0, 1.0) = {raw:.2f}"
            )
        if hasattr(self, '_last_stats'):
            avg_atk, avg_dfn, fragility = self._last_stats
            return (
                f"Ataque promedio = {avg_atk:.2f}\n"
                f"Defensa promedio = {avg_dfn:.2f} → fragilidad = {fragility:.2f}\n"
                f"Fórmula: (atk×2 + fragilidad + atk×fragilidad) / 4\n"
                f"= ({avg_atk:.2f}×2 + {fragility:.2f} + {avg_atk:.2f}×{fragility:.2f}) / 4 = {raw:.2f}"
            )
        return ""
