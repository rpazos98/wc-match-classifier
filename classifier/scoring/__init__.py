import math as _math
from dataclasses import dataclass, field
from ..models import Match, UserProfile, ScoringResult


@dataclass
class MatchPrediction:
    """
    Pre-computed ELO-based probabilities for a match.
    Computed once per match in ScoringEngine.evaluate() and shared
    across all scorers via ScoringContext — no scorer should call
    win_probability() or current_elo() directly.
    """
    p_home:     float   # P(home win)
    p_draw:     float   # P(draw)
    p_away:     float   # P(away win)
    elo_home:   float   # current ELO for home team
    elo_away:   float   # current ELO for away team
    entropy:    float   # normalised Shannon entropy H/log(3)  — 0=certain, 1=max uncertainty
    p_underdog: float   # min(p_home, p_away) / (p_home+p_away) — underdog's decisive prob

    @classmethod
    def compute(cls, home: str, away: str) -> "MatchPrediction":
        from classifier.elo import win_probability, current_elo
        p_h, p_d, p_a = win_probability(home, away, neutral=True)
        H = -sum(p * _math.log(p) for p in (p_h, p_d, p_a) if p > 0)
        total_dec = p_h + p_a
        p_under = min(p_h, p_a) / total_dec if total_dec > 0 else 0.5
        return cls(
            p_home=p_h, p_draw=p_d, p_away=p_a,
            elo_home=current_elo(home), elo_away=current_elo(away),
            entropy=H / _math.log(3),
            p_underdog=p_under,
        )

    @classmethod
    def neutral(cls) -> "MatchPrediction":
        """Fallback when one or both teams are TBD."""
        H = -3 * (1/3 * _math.log(1/3))
        return cls(p_home=0.35, p_draw=0.30, p_away=0.35,
                   elo_home=1500.0, elo_away=1500.0,
                   entropy=1.0, p_underdog=0.5)


@dataclass
class ScoringContext:
    match:                Match
    profile:              UserProfile
    predicted_home_goals: int | None = None
    predicted_away_goals: int | None = None
    prediction:           MatchPrediction | None = None


class BaseScorer:
    name:   str
    weight: float  # contribution weight; all scorers should sum to 1.0

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        """Return (raw_score 0.0–1.0, reason_string)."""
        raise NotImplementedError


class ScoringEngine:
    def __init__(self, scorers: list[BaseScorer]):
        total = sum(s.weight for s in scorers)
        assert abs(total - 1.0) < 1e-9, f"Scorer weights must sum to 1.0, got {total}"
        self.scorers = scorers

    def evaluate(
        self,
        match: Match,
        profile: UserProfile,
        predicted_home_goals: int | None = None,
        predicted_away_goals: int | None = None,
    ) -> ScoringResult:
        # Pre-compute ELO prediction once, shared across all scorers
        if match.home != "TBD" and match.away != "TBD":
            prediction = MatchPrediction.compute(match.home, match.away)
        else:
            prediction = MatchPrediction.neutral()

        ctx = ScoringContext(
            match=match,
            profile=profile,
            predicted_home_goals=predicted_home_goals,
            predicted_away_goals=predicted_away_goals,
            prediction=prediction,
        )
        breakdown:        dict[str, float] = {}
        reason_by_scorer: dict[str, str]   = {}
        raw_by_scorer:    dict[str, float] = {}
        weight_by_scorer: dict[str, float] = {}
        reasons:          list[str]        = []
        total = 0.0

        for scorer in self.scorers:
            raw, reason = scorer.score(ctx)
            contribution = raw * scorer.weight * 100
            breakdown[scorer.name]        = contribution
            reason_by_scorer[scorer.name] = reason
            raw_by_scorer[scorer.name]    = raw
            weight_by_scorer[scorer.name] = scorer.weight
            total += contribution
            if reason:
                reasons.append(reason)

        pred_dict = None
        if prediction is not None:
            pred_dict = {
                "p_home":   round(prediction.p_home, 3),
                "p_draw":   round(prediction.p_draw, 3),
                "p_away":   round(prediction.p_away, 3),
                "elo_home": round(prediction.elo_home),
                "elo_away": round(prediction.elo_away),
                "entropy":  round(prediction.entropy, 3),
            }

        return ScoringResult(
            match=match,
            total_score=min(total, 100.0),
            breakdown=breakdown,
            reasons=reasons,
            reason_by_scorer=reason_by_scorer,
            raw_by_scorer=raw_by_scorer,
            weight_by_scorer=weight_by_scorer,
            prediction=pred_dict,
        )

    def evaluate_all(
        self,
        matches: list[Match],
        profile: UserProfile,
        predicted_scores: dict[str, tuple[int, int]] | None = None,
    ) -> list[ScoringResult]:
        results = []
        for m in matches:
            phg = pag = None
            if predicted_scores and m.match_id in predicted_scores:
                phg, pag = predicted_scores[m.match_id]
            results.append(self.evaluate(m, profile, phg, pag))
        results.sort(key=lambda r: r.total_score, reverse=True)
        return results
