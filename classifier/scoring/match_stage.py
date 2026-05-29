from functools import lru_cache
from . import BaseScorer, ScoringContext
from ..models import Stage

_STAGE_SCORES: dict[Stage, float] = {
    Stage.R32:   0.40,
    Stage.R16:   0.55,
    Stage.QF:    0.75,
    Stage.SF:    0.90,
    Stage.THIRD: 0.60,
    Stage.FINAL: 1.00,
}

_GROUP_MD_SCORES = {1: 0.20, 2: 0.28, 3: 0.42}

_STAGE_LABELS: dict[Stage, str] = {
    Stage.GROUP: "Group Stage",
    Stage.R32:   "Round of 32",
    Stage.R16:   "Round of 16",
    Stage.QF:    "Quarter-finals",
    Stage.SF:    "Semi-finals",
    Stage.THIRD: "Third place",
    Stage.FINAL: "Grand Final!",
}

_MD_LABELS = {1: "Matchday 1", 2: "Matchday 2", 3: "Matchday 3 — Group decider!"}


@lru_cache(maxsize=1)
def _matchdays() -> dict[int, int]:
    from db.query import group_match_matchdays
    return group_match_matchdays()


class MatchStageScorer(BaseScorer):
    name   = "Match Stage"
    weight = 0.17
    literature = [
        "Jennett (1984) — match significance (contention for a prize) drives attendance",
        "Buraimo & Forrest (2025) — significance is one of the most robust predictors across 4 leagues",
        "Csato (2025) — tournament attractiveness as explicit design criterion",
    ]

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        stage = ctx.match.stage

        if stage == Stage.GROUP:
            mn  = int(ctx.match.match_id[1:])
            md  = _matchdays().get(mn, 2)
            raw = _GROUP_MD_SCORES[md]

            # J3 dynamic: competitive matches matter more (both teams need a result)
            if md == 3 and ctx.prediction:
                entropy = ctx.prediction.entropy
                # entropy=1.0 → boost to 0.54, entropy=0.5 → stays 0.42, entropy=0.2 → drops to 0.37
                raw *= (0.8 + 0.4 * entropy)

            return raw, _MD_LABELS[md]

        raw   = _STAGE_SCORES[stage]
        label = _STAGE_LABELS[stage]
        return raw, label

    def detail(self, ctx: ScoringContext, raw: float) -> str:
        stage = ctx.match.stage
        label = _STAGE_LABELS.get(stage, stage.value)
        scores = {
            "Group MD1": 0.20, "Group MD2": 0.28, "Group MD3": "0.42 × competitiveness",
            "R32": 0.40, "R16": 0.55, "QF": 0.75,
            "SF": 0.90, "3rd place": 0.60, "Final": 1.00,
        }
        table = " | ".join(f"{k}={v}" for k, v in scores.items())
        lines = f"Stage: {label} → raw = {raw:.2f}\nScale: {table}"
        if stage == Stage.GROUP:
            mn = int(ctx.match.match_id[1:])
            md = _matchdays().get(mn, 2)
            if md == 3 and ctx.prediction:
                e = ctx.prediction.entropy
                lines += f"\nMD3 dynamic: entropy = {e:.2f} → factor = {0.8 + 0.4*e:.2f}"
        return lines
