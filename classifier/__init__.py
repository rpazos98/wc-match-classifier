from .models import UserProfile, Match, Squad, Stage, TimeWindow, ScoringResult
from .scoring import ScoringEngine
from .scoring.favorite_team import FavoriteTeamScorer
from .scoring.favorite_player import FavoritePlayerScorer
from .scoring.match_stage import MatchStageScorer
from .scoring.competitive_tension import CompetitiveTensionScorer
from .scoring.chaos_potential import ChaosPotentialScorer
from .scoring.upset_potential import UpsetPotentialScorer
from .scoring.narrative import NarrativeScorer
from .scoring.form import FormScorer
from .scoring.star_power import StarPowerScorer
from .scoring.same_group import SameGroupScorer
from .classification import classify_all, Classification


def build_default_engine() -> ScoringEngine:
    # TimeAvailability removed: availability is a filter, not a preference
    # signal — if your team plays at 3am you still watch.
    #
    # Its 0.10 redistributed: +0.03 Stage, +0.02 Tension,
    # +0.02 Chaos, +0.01 FavTeam, +0.01 Form, +0.01 Upset.
    #
    # Sum = 0.19+0.18+0.18+0.14+0.07+0.06+0.06+0.05+0.04+0.03 = 1.00
    return ScoringEngine([
        FavoriteTeamScorer(),           # 0.19
        MatchStageScorer(),             # 0.18
        CompetitiveTensionScorer(),     # 0.18
        ChaosPotentialScorer(),         # 0.14
        FavoritePlayerScorer(),         # 0.07
        UpsetPotentialScorer(),         # 0.06
        FormScorer(),                   # 0.06  (was 0.08 → trimmed for headroom)
        StarPowerScorer(),              # 0.05
        NarrativeScorer(),              # 0.04
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
    predicted_scores: dict[str, tuple[int, int]] | None = None,
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
