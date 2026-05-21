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
    Stage.GROUP: "Fase de grupos",
    Stage.R32:   "Ronda de 32",
    Stage.R16:   "Octavos de final",
    Stage.QF:    "Cuartos de final",
    Stage.SF:    "Semifinal",
    Stage.THIRD: "Tercer lugar",
    Stage.FINAL: "¡Gran Final!",
}

_MD_LABELS = {1: "Jornada 1", 2: "Jornada 2", 3: "Jornada 3 — ¡Se define el grupo!"}


@lru_cache(maxsize=1)
def _matchdays() -> dict[int, int]:
    from db.query import group_match_matchdays
    return group_match_matchdays()


class MatchStageScorer(BaseScorer):
    name   = "Match Stage"
    weight = 0.18

    def score(self, ctx: ScoringContext) -> tuple[float, str]:
        stage = ctx.match.stage

        if stage == Stage.GROUP:
            mn  = int(ctx.match.match_id[1:])
            md  = _matchdays().get(mn, 2)
            raw = _GROUP_MD_SCORES[md]
            return raw, _MD_LABELS[md]

        raw   = _STAGE_SCORES[stage]
        label = _STAGE_LABELS[stage]
        return raw, label
