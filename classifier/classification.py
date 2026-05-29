from dataclasses import dataclass
from .models import ScoringResult

THRESHOLD_IMPERDIBLE = 60.0
THRESHOLD_VALE       = 30.0

LABEL_IMPERDIBLE = "Must Watch"
LABEL_VALE       = "Worth Watching"
LABEL_RESUMEN    = "Catch the Highlights"

EMOJI = {
    LABEL_IMPERDIBLE: "🔥",
    LABEL_VALE:       "👀",
    LABEL_RESUMEN:    "📺",
}


@dataclass(slots=True)
class Classification:
    result: ScoringResult
    label:  str
    emoji:  str


def classify(result: ScoringResult) -> Classification:
    if result.total_score >= THRESHOLD_IMPERDIBLE:
        label = LABEL_IMPERDIBLE
    elif result.total_score >= THRESHOLD_VALE:
        label = LABEL_VALE
    else:
        label = LABEL_RESUMEN
    result.label = label
    return Classification(result=result, label=label, emoji=EMOJI[label])


def classify_all(results: list[ScoringResult]) -> list[Classification]:
    return [classify(r) for r in results]
