from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from zoneinfo import ZoneInfo


class Stage(Enum):
    GROUP = "group"
    R32   = "r32"
    R16   = "r16"
    QF    = "qf"
    SF    = "sf"
    THIRD = "third_place"
    FINAL = "final"


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start_hour: int       # local time 0-23
    end_hour:   int       # local time 0-23 (exclusive)
    timezone:   ZoneInfo
    weekday:    int | None = None   # 0=Mon..6=Sun; None means every day
    date:       date | None = None  # overrides weekday if set


@dataclass(slots=True)
class UserProfile:
    name:             str
    team_affinities:  dict[str, float]  # ISO code → 0.0–1.0 (S=1.0, A=0.65, B=0.3)
    time_windows:     list[TimeWindow]
    language:         str = "es"
    region:           str = "MX"


@dataclass(frozen=True, slots=True)
class Squad:
    team_code: str
    players:   tuple[str, ...]       # frozen tuple for hashability


@dataclass(frozen=True, slots=True)
class Match:
    match_id:    str
    home:        str        # team code
    away:        str        # team code
    kickoff_utc: datetime   # always UTC
    stage:       Stage
    venue:       str
    home_squad:  Squad | None = None
    away_squad:  Squad | None = None


@dataclass(slots=True)
class ScoringResult:
    match:             Match
    total_score:       float              # 0.0 – 100.0
    breakdown:         dict[str, float]   # scorer_name -> contribution pts
    reasons:           list[str]          # flat list (kept for compat)
    reason_by_scorer:  dict[str, str]     # scorer_name -> reason string
    raw_by_scorer:     dict[str, float]   # scorer_name -> raw 0.0–1.0
    weight_by_scorer:  dict[str, float]   # scorer_name -> weight used
    detail_by_scorer:  dict[str, str] | None = None  # scorer_name -> calc explanation
    prediction:        dict | None = None # {p_home, p_draw, p_away, elo_home, elo_away, entropy}
    label:             str = ""           # set after classification
