from . import BaseScorer, ScoringContext
from ..models import Stage

_STAGE_SCORES: dict[Stage, float] = {
    Stage.GROUP: 0.25,
    Stage.R32:   0.40,
    Stage.R16:   0.55,
    Stage.QF:    0.75,
    Stage.SF:    0.90,
    Stage.THIRD: 0.60,
    Stage.FINAL: 1.00,
}

_STAGE_LABELS: dict[Stage, str] = {
    Stage.GROUP: "Fase de grupos",
    Stage.R32:   "Ronda de 32",
    Stage.R16:   "Octavos de final",
    Stage.QF:    "Cuartos de final",
    Stage.SF:    "Semifinal",
    Stage.THIRD: "Tercer lugar",
    Stage.FINAL: "¡Gran Final!",
}


class MatchStageScorer(BaseScorer):
    name   = "Match Stage"
    weight = 0.10

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        stage = ctx.match.stage
        raw   = _STAGE_SCORES[stage]
        label = _STAGE_LABELS[stage]
        return raw, label
