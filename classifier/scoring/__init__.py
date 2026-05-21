from dataclasses import dataclass
from ..models import Match, UserProfile, ScoringResult


@dataclass
class ScoringContext:
    match:   Match
    profile: UserProfile


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

    def evaluate(self, match: Match, profile: UserProfile) -> ScoringResult:
        ctx = ScoringContext(match=match, profile=profile)
        breakdown:        dict[str, float] = {}
        reason_by_scorer: dict[str, str]   = {}
        raw_by_scorer:    dict[str, float] = {}
        reasons:          list[str]        = []
        total = 0.0

        for scorer in self.scorers:
            raw, reason = scorer.score(ctx)
            contribution = raw * scorer.weight * 100
            breakdown[scorer.name]        = contribution
            reason_by_scorer[scorer.name] = reason
            raw_by_scorer[scorer.name]    = raw
            total += contribution
            if reason:
                reasons.append(reason)

        return ScoringResult(
            match=match,
            total_score=min(total, 100.0),
            breakdown=breakdown,
            reasons=reasons,
            reason_by_scorer=reason_by_scorer,
            raw_by_scorer=raw_by_scorer,
        )

    def evaluate_all(self, matches: list[Match], profile: UserProfile) -> list[ScoringResult]:
        results = [self.evaluate(m, profile) for m in matches]
        results.sort(key=lambda r: r.total_score, reverse=True)
        return results
