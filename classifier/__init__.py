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
from .classification import classify_all, Classification


def build_default_engine() -> ScoringEngine:
    # Weights (sum = 1.00):
    #   FavTeam=0.28, TimeAvail=0.21, Stage=0.12, Form=0.11,
    #   FavPlayer=0.08, DarkHorse=0.07, SameGroup=0.06,
    #   TeamStrength=0.04, Rivalry=0.02, Confederation=0.01
    return ScoringEngine([
        FavoriteTeamScorer(),
        TimeAvailabilityScorer(),
        MatchStageScorer(),
        FormScorer(),
        FavoritePlayerScorer(),
        DarkHorseScorer(),
        SameGroupScorer(),
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