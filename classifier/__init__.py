from .models import UserProfile, Match, Squad, Stage, TimeWindow, ScoringResult
from .scoring import ScoringEngine
from .scoring.favorite_team import FavoriteTeamScorer
from .scoring.match_stage import MatchStageScorer
from .scoring.competitive_tension import CompetitiveTensionScorer
from .scoring.chaos_potential import ChaosPotentialScorer
from .scoring.narrative import NarrativeScorer
from .scoring.form import FormScorer
from .scoring.star_power import StarPowerScorer
from .scoring.same_group import SameGroupScorer
from .classification import classify_all, Classification


def build_default_engine() -> ScoringEngine:
    # Weights informed by sports economics literature:
    # - Quality > closeness: Buraimo & Simmons (2015), Cox (2023)
    # - Stakes robust: Jennett (1984), Buraimo & Forrest (2025)
    # - Rivalry mixed: Tyler et al. (2024)
    # See research/literature_review.md for full references.
    #
    # Sum = 0.19+0.18+0.17+0.17+0.12+0.08+0.06+0.03 = 1.00
    return ScoringEngine([
        FavoriteTeamScorer(),           # 0.19
        CompetitiveTensionScorer(),     # 0.18 (was 0.21)
        MatchStageScorer(),             # 0.17
        StarPowerScorer(),              # 0.17 (was 0.14)
        ChaosPotentialScorer(),         # 0.12
        FormScorer(),                   # 0.08
        NarrativeScorer(),              # 0.06
        SameGroupScorer(),              # 0.03
    ])


def apply_learned_weights(engine: ScoringEngine, weights: dict[str, float]) -> None:
    """Mutate scorer weights in-place. Weights are re-normalised to sum=1."""
    total = sum(weights.get(s.name, s.weight) for s in engine.scorers)
    if total > 0:
        for s in engine.scorers:
            s.weight = weights.get(s.name, s.weight) / total


def classify_matches(
    matches: list[Match],
    profile: UserProfile,
    predicted_scores: dict[str, tuple[float, float]] | None = None,
    learned_weights: dict[str, float] | None = None,
) -> list[Classification]:
    engine = build_default_engine()
    if learned_weights:
        apply_learned_weights(engine, learned_weights)
    results = engine.evaluate_all(matches, profile, predicted_scores)
    return classify_all(results)


def load_all_matches() -> list[Match]:
    from db.query import load_matches
    return load_matches()
