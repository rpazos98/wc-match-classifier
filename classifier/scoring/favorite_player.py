from functools import lru_cache
from . import BaseScorer, ScoringContext


@lru_cache(maxsize=1)
def _goals_map() -> dict[str, int]:
    from db.query import player_goals_map
    return player_goals_map()


@lru_cache(maxsize=1)
def _long_names() -> dict[str, str]:
    from db.query import player_long_names
    return player_long_names()


def _player_weight(short_name: str) -> float:
    """0.5–1.0 based on international goals. No goals data → 0.5 baseline."""
    long = _long_names().get(short_name)
    goals = _goals_map().get(long or short_name, 0)
    if goals >= 30:
        return 1.0
    if goals >= 15:
        return 0.85
    if goals >= 5:
        return 0.7
    if goals > 0:
        return 0.6
    return 0.5


def _find_exact(fav_lower: list[str], squads) -> list[tuple[str, float]]:
    """Substring match: returns (short_name, weight) pairs."""
    found: list[tuple[str, float]] = []
    for squad in squads:
        for player in squad.players:
            for fav in fav_lower:
                if fav in player.lower():
                    found.append((player, _player_weight(player)))
                    break
    return found


def _find_similar(
    fav_names: list[str],
    squads,
    min_sim: float = 0.88,
) -> list[tuple[str, str, float]]:
    """
    Embedding fallback: returns (fav_name, similar_squad_player, similarity) triples.
    Skips gracefully if numpy/embeddings unavailable.
    """
    try:
        from classifier.embeddings import get_index
        idx = get_index()
    except Exception:
        return []

    results: list[tuple[str, str, float]] = []
    all_squad_players: tuple[str, ...] = tuple(
        p for s in squads for p in s.players
    )
    for fav in fav_names:
        match = idx.best_match_in_squad(fav, all_squad_players, min_sim=min_sim)
        if match:
            similar_player, sim = match
            results.append((fav, similar_player, sim))
    return results


class FavoritePlayerScorer(BaseScorer):
    name   = "Favorite Player"
    weight = 0.07

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        squads = [s for s in (ctx.match.home_squad, ctx.match.away_squad) if s]
        if not squads:
            return 0.5, ""  # abstain: squads unknown

        fav_lower = [p.lower() for p in ctx.profile.favorite_players]

        # ── Exact / substring match (original behaviour) ──────────────────────
        found = _find_exact(fav_lower, squads)
        if found:
            raw = max(w for _, w in found)
            if len(found) >= 2:
                raw = min(1.0, raw + 0.15)
            names  = ", ".join(p for p, _ in found[:3])
            suffix = " (más)" if len(found) > 3 else ""
            return raw, f"{names}{suffix} (jugadores favoritos) en la cancha"

        # ── Embedding similarity fallback ─────────────────────────────────────
        similar = _find_similar(ctx.profile.favorite_players, squads)
        if not similar:
            return 0.0, ""

        # Score: similarity * 0.6 → max ~0.6 (always below an exact match at 0.5+)
        best_fav, best_match, best_sim = max(similar, key=lambda t: t[2])
        raw = best_sim * 0.6

        reason = (
            f"{best_match} (estilo similar a {best_fav}, "
            f"similitud {best_sim:.0%})"
        )
        return raw, reason
