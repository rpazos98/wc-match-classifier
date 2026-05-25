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
    predicted_home_goals: float | None = None
    predicted_away_goals: float | None = None
    prediction:           MatchPrediction | None = None


class BaseScorer:
    name:       str
    weight:     float         # contribution weight; all scorers should sum to 1.0
    literature: list[str] = []  # key paper references backing this scorer

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        """Return (raw_score 0.0–1.0, reason_string)."""
        raise NotImplementedError

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        """Optional: return multi-line calculation breakdown for the UI."""
        return ""


class ScoringEngine:
    def __init__(self, scorers: list[BaseScorer]):
        total = sum(s.weight for s in scorers)
        assert abs(total - 1.0) < 1e-9, f"Scorer weights must sum to 1.0, got {total}"
        self.scorers = scorers

    def evaluate(
        self,
        match: Match,
        profile: UserProfile,
        predicted_home_goals: float | None = None,
        predicted_away_goals: float | None = None,
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
        detail_by_scorer: dict[str, str]   = {}
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
            det = scorer.detail(ctx, raw)
            if det:
                detail_by_scorer[scorer.name] = det

        # ── Synergy: your team in a big match is more than the sum ────
        fav_raw   = raw_by_scorer.get("Favorite Team", 0)
        stage_raw = raw_by_scorer.get("Match Stage", 0)
        if fav_raw > 0.3 and stage_raw > 0.35:
            synergy = fav_raw * stage_raw * 8.0  # up to 8 bonus pts
            total += synergy
            breakdown["Momento"]        = round(synergy, 1)
            raw_by_scorer["Momento"]    = round(fav_raw * stage_raw, 4)
            weight_by_scorer["Momento"] = 0.08
            reason_by_scorer["Momento"] = "Tu equipo en un partido importante"
            detail_by_scorer["Momento"] = (
                f"Afinidad equipo = {fav_raw:.2f}, importancia etapa = {stage_raw:.2f}\n"
                f"Bonus = afinidad × etapa × 8\n"
                f"= {fav_raw:.2f} × {stage_raw:.2f} × 8 = {synergy:.1f} pts extra"
            )

        # ── Synergy: close + high-scoring = disproportionate excitement ──
        # Vecer (2007): excitement ∝ win-probability total variation,
        # which depends on BOTH scoring rate and closeness interacting.
        tension_raw = raw_by_scorer.get("Competitive Tension", 0)
        chaos_raw   = raw_by_scorer.get("Chaos Potential", 0)
        if tension_raw > 0.45 and chaos_raw > 0.45:
            vecer = tension_raw * chaos_raw * 6.0  # up to 6 bonus pts
            total += vecer
            breakdown["Espectáculo"]        = round(vecer, 1)
            raw_by_scorer["Espectáculo"]    = round(tension_raw * chaos_raw, 4)
            weight_by_scorer["Espectáculo"] = 0.06
            reason_by_scorer["Espectáculo"] = "Partido cerrado y con goles — alto potencial de emoción"
            detail_by_scorer["Espectáculo"] = (
                f"Tensión competitiva = {tension_raw:.2f}, Potencial caótico = {chaos_raw:.2f}\n"
                f"Referencia: Vecer (2007) — excitación ∝ goles × paridad\n"
                f"Bonus = tensión × caos × 6 = {vecer:.1f} pts"
            )

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
            detail_by_scorer=detail_by_scorer or None,
            prediction=pred_dict,
        )

    def evaluate_all(
        self,
        matches: list[Match],
        profile: UserProfile,
        predicted_scores: dict[str, tuple[float, float]] | None = None,
    ) -> list[ScoringResult]:
        results = []
        for m in matches:
            phg = pag = None
            if predicted_scores and m.match_id in predicted_scores:
                phg, pag = predicted_scores[m.match_id]
            results.append(self.evaluate(m, profile, phg, pag))
        results.sort(key=lambda r: r.total_score, reverse=True)
        return results
