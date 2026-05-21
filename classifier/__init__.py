from .models import UserProfile, Match, Squad, Stage, TimeWindow, ScoringResult
from .scoring import ScoringEngine
from .scoring.favorite_team import FavoriteTeamScorer
from .scoring.favorite_player import FavoritePlayerScorer
from .scoring.time_availability import TimeAvailabilityScorer
from .scoring.match_stage import MatchStageScorer
from .scoring.rivalry import RivalryScorer
from .scoring.team_strength import TeamStrengthScorer
from .scoring.form import FormScorer
from .scoring.dark_horse import DarkHorseScorer
from .scoring.confederation import ConfederationScorer
from .scoring.same_group import SameGroupScorer
from .scoring.match_drama import MatchDramaScorer
from .scoring.goal_fest import GoalFestScorer
from .scoring.upset_potential import UpsetPotentialScorer
from .scoring.narrative_weight import NarrativeWeightScorer
from .classification import classify_all, Classification


def build_default_engine() -> ScoringEngine:
    # Weights (sum = 1.00):
    #   FavTeam=0.22, TimeAvail=0.15, Stage=0.10, Form=0.09,
    #   FavPlayer=0.07, MatchDrama=0.08, GoalFest=0.06, DarkHorse=0.05,
    #   UpsetPotential=0.05, SameGroup=0.04, NarrativeWeight=0.04,
    #   TeamStrength=0.03, Rivalry=0.01, Confederation=0.01
    return ScoringEngine([
        FavoriteTeamScorer(),
        TimeAvailabilityScorer(),
        MatchStageScorer(),
        FormScorer(),
        FavoritePlayerScorer(),
        MatchDramaScorer(),
        GoalFestScorer(),
        DarkHorseScorer(),
        UpsetPotentialScorer(),
        SameGroupScorer(),
        NarrativeWeightScorer(),
        TeamStrengthScorer(),
        RivalryScorer(),
        ConfederationScorer(),
    ])


def classify_matches(
    matches: list[Match],
    profile: UserProfile,
) -> list[Classification]:
    engine = build_default_engine()
    results = engine.evaluate_all(matches, profile)
    return classify_all(results)


def load_all_matches() -> list[Match]:
    from db.query import load_matches
    return load_matches()