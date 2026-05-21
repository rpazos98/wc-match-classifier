"""
Historical World Cup match pairs for preference learning.

Uses data/wc_history/matches_1930_2022.csv (2018 & 2022 by default) to present
the user with memorable, known matches, yielding stronger preference signal
than hypothetical 2026 fixtures.

Feature extraction is intentionally partial: time availability, form, team
strength, and dark-horse are set to neutral (0.5 / 0.0) since that context
is not available historically.  The logistic regression still learns from the
features that DO vary: stage, favorite team, rivalry, same group, and favorite
player presence.
"""
from __future__ import annotations

import csv
import random
import re
from functools import lru_cache
from pathlib import Path

from .models import UserProfile
from .learning import SCORER_NAMES

# ── Name → FIFA code ──────────────────────────────────────────────────────────

_NAME_TO_CODE: dict[str, str] = {
    "Argentina":      "ARG", "Brazil":         "BRA", "France":    "FRA",
    "Germany":        "GER", "Spain":          "ESP", "England":   "ENG",
    "Portugal":       "POR", "Netherlands":    "NED", "Uruguay":   "URU",
    "Colombia":       "COL", "Morocco":        "MAR", "United States": "USA",
    "Croatia":        "CRO", "Switzerland":    "SUI", "Belgium":   "BEL",
    "Japan":          "JPN", "Korea Republic": "KOR", "Australia": "AUS",
    "Canada":         "CAN", "Ecuador":        "ECU", "Senegal":   "SEN",
    "Ghana":          "GHA", "Nigeria":        "NGA", "Cameroon":  "CMR",
    "Egypt":          "EGY", "Mexico":         "MEX", "Poland":    "POL",
    "Denmark":        "DEN", "Serbia":         "SRB", "Sweden":    "SWE",
    "Iceland":        "ISL", "Russia":         "RUS", "Peru":      "PER",
    "Panama":         "PAN", "Tunisia":        "TUN", "Costa Rica":"CRC",
    "Wales":          "WAL", "Qatar":          "QAT", "Saudi Arabia": "KSA",
    "IR Iran":        "IRN", "Ivory Coast":    "CIV", "Algeria":   "ALG",
    "Austria":        "AUT", "Norway":         "NOR", "Scotland":  "SCO",
    "Jordan":         "JOR", "Uzbekistan":     "UZB", "Curacao":   "CUR",
    "Paraguay":       "PAR", "Bosnia and Herzegovina": "BIH",
    "Turkey":         "TUR", "Czech Republic": "CZE",
    "Cape Verde":     "CPV", "DR Congo":       "COD",
}


def name_to_code(name: str) -> str | None:
    return _NAME_TO_CODE.get(name)


# ── Stage → raw score ─────────────────────────────────────────────────────────

_ROUND_RAW: dict[str, float] = {
    "Group stage":          0.25,
    "First round":          0.25,
    "Group stage play-off": 0.25,
    "Round of 16":          0.55,
    "Second round":         0.40,
    "Quarter-finals":       0.75,
    "Semi-finals":          0.90,
    "Third-place match":    0.60,
    "Final stage":          0.85,
    "Final":                1.00,
}

_ROUND_LABEL: dict[str, str] = {
    "Group stage":          "Fase de grupos",
    "First round":          "Primera ronda",
    "Round of 16":          "16avos",
    "Quarter-finals":       "Cuartos",
    "Semi-finals":          "Semifinal",
    "Third-place match":    "3er lugar",
    "Final":                "Final",
}


# ── Data loading ──────────────────────────────────────────────────────────────

_DATA_PATH = Path(__file__).parent.parent / "data" / "wc_history" / "matches_1930_2022.csv"


@lru_cache(maxsize=1)
def _load_history() -> list[dict]:
    rows = []
    with open(_DATA_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


# ── Rivalry lookup ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _wc_h2h() -> dict[tuple[str, str], float]:
    try:
        from db.query import wc_h2h_scores
        return wc_h2h_scores()
    except Exception:
        return {}

@lru_cache(maxsize=1)
def _rivals() -> dict[str, set[str]]:
    try:
        from db.query import wc_rivals
        return wc_rivals()
    except Exception:
        return {}

@lru_cache(maxsize=1)
def _wc_meetings() -> dict[frozenset, int]:
    try:
        from db.query import wc_h2h_meetings
        return wc_h2h_meetings()
    except Exception:
        return {}

@lru_cache(maxsize=1)
def _quality_scores() -> dict[str, float]:
    try:
        from db.query import team_quality_scores
        return team_quality_scores()
    except Exception:
        return {}


def _rivalry_raw(code_a: str, code_b: str) -> float:
    h2h  = _wc_h2h()
    pair = (min(code_a, code_b), max(code_a, code_b))
    raw  = h2h.get(pair, 0.0)
    if raw >= 0.1:
        return raw
    return 0.0


def _is_rival(code: str, favs: set[str]) -> bool:
    rv = _rivals()
    return any(code in rv.get(f, set()) for f in favs)


# ── Goal scorer parsing ───────────────────────────────────────────────────────

def _scorer_names(goal_str: str) -> list[str]:
    """Parse 'Messi · 36|Di María · 108' → ['messi', 'di maría']"""
    if not goal_str:
        return []
    names = []
    for part in goal_str.split("|"):
        # format: "Name · minute" or just "Name"
        name = re.split(r"·|\d", part)[0].strip().lower()
        if name:
            names.append(name)
    return names


def _fav_player_raw(home_goal: str, away_goal: str, fav_players: list[str]) -> float:
    scorers = set(_scorer_names(home_goal) + _scorer_names(away_goal))
    for fav in fav_players:
        fav_lower = fav.lower()
        if any(fav_lower in s or s in fav_lower for s in scorers if len(s) > 2):
            return 0.8
    return 0.0


# ── Feature extraction ────────────────────────────────────────────────────────

def _extract_features(row: dict, profile: UserProfile) -> dict[str, float]:
    home_code = name_to_code(row["home_team"])
    away_code = name_to_code(row["away_team"])
    favs = {t.upper() for t in profile.favorite_teams}

    # Favorite Team
    fav_team_raw = 0.0
    if home_code in favs or away_code in favs:
        fav_team_raw = 1.0
    elif home_code and _is_rival(home_code, favs):
        fav_team_raw = 0.35
    elif away_code and _is_rival(away_code, favs):
        fav_team_raw = 0.35

    # Match Stage
    stage_raw = _ROUND_RAW.get(row["Round"], 0.5)

    # Rivalry
    rivalry_raw = 0.0
    if home_code and away_code:
        rivalry_raw = _rivalry_raw(home_code, away_code)

    # Favorite Player (from goal scorers)
    fp_raw = _fav_player_raw(
        row.get("home_goal", ""),
        row.get("away_goal", ""),
        profile.favorite_players,
    )

    # Match Drama: margin + penalty bonus
    try:
        hs      = int(float(row.get("home_score", 0) or 0))
        as_     = int(float(row.get("away_score", 0) or 0))
        margin  = abs(hs - as_)
        base    = {0: 1.0, 1: 0.75, 2: 0.40}.get(margin, 0.10)
        pen     = bool(row.get("home_penalty", ""))
        drama_raw = min(1.0, base + (0.25 if pen else 0.0))
    except (ValueError, TypeError):
        drama_raw = 0.5

    # Goal Fest: total goals scored
    try:
        total_goals   = int(float(row.get("home_score", 0) or 0)) + int(float(row.get("away_score", 0) or 0))
        goal_fest_raw = min(1.0, total_goals / 5.0)
    except (ValueError, TypeError):
        goal_fest_raw = 0.5

    # Upset Potential: quality gap proxy (current ratings as historical approximation)
    quality = _quality_scores()
    q_home  = quality.get(home_code, 0.5) if home_code else 0.5
    q_away  = quality.get(away_code, 0.5) if away_code else 0.5
    upset_raw = min(1.0, abs(q_home - q_away) * 2)

    # Narrative Weight: WC meeting count
    pair          = frozenset({home_code, away_code}) if home_code and away_code else frozenset()
    n_meetings    = _wc_meetings().get(pair, 0)
    if n_meetings == 0:   narrative_raw = 0.4
    elif n_meetings <= 2: narrative_raw = 0.55
    elif n_meetings <= 4: narrative_raw = 0.70
    elif n_meetings <= 6: narrative_raw = 0.85
    else:                 narrative_raw = 1.0

    return {
        "Favorite Team":     fav_team_raw,
        "Time Availability": 0.5,         # neutral — not applicable historically
        "Match Stage":       stage_raw,
        "Form":              0.5,         # neutral
        "Favorite Player":   fp_raw,
        "Match Drama":       drama_raw,
        "Goal Fest":         goal_fest_raw,
        "Dark Horse":        0.0,         # skip
        "Upset Potential":   upset_raw,
        "Same Group":        fav_team_raw if row["Round"] in ("Group stage", "First round") else 0.0,
        "Narrative Weight":  narrative_raw,
        "Team Strength":     0.5,         # neutral
        "Rivalry":           rivalry_raw,
        "Confederation":     0.0,         # skip
    }


# ── Public API ────────────────────────────────────────────────────────────────

def sample_historical_pairs(
    profile: UserProfile,
    n: int = 6,
    years: list[int] | None = None,
    seed: int | None = None,
) -> list[dict]:
    """
    Return n historical WC match pairs for preference elicitation.
    Each pair has the same structure as sample_pairs() plus 'historical': True,
    actual scores, and goal scorer info for richer display.
    """
    if years is None:
        years = [2018, 2022]

    year_set = {str(y) for y in years}
    history  = _load_history()

    candidates = [
        r for r in history
        if r["Year"] in year_set
        and r["home_score"] not in ("", "NA")
        and r["away_score"] not in ("", "NA")
        and name_to_code(r["home_team"]) is not None
        and name_to_code(r["away_team"]) is not None
    ]

    if len(candidates) < 2:
        return []

    rng  = random.Random(seed)
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[dict, dict]] = []

    # Prioritise matches involving fav team or high-stage matches for richer signal
    favs      = {t.upper() for t in profile.favorite_teams}
    fav_rows  = [r for r in candidates if name_to_code(r["home_team"]) in favs
                                       or name_to_code(r["away_team"]) in favs]
    late_rows = [r for r in candidates if _ROUND_RAW.get(r["Round"], 0) >= 0.75]
    seen_ids  = set()
    pool      = []
    for r in fav_rows + late_rows + candidates:
        rid = r["Date"] + r["home_team"]
        if rid not in seen_ids:
            seen_ids.add(rid)
            pool.append(r)

    attempts = 0
    while len(pairs) < n and attempts < n * 30:
        a, b = rng.sample(pool, 2)
        key  = tuple(sorted([a["Date"] + a["home_team"], b["Date"] + b["home_team"]]))
        if key not in seen:
            seen.add(key)
            if rng.random() < 0.5:
                a, b = b, a
            pairs.append((a, b))
        attempts += 1

    def _info(row: dict) -> dict:
        hc = name_to_code(row["home_team"])
        ac = name_to_code(row["away_team"])
        hs = row.get("home_score", "?")
        as_ = row.get("away_score", "?")
        hp = row.get("home_penalty", "")
        ap = row.get("away_penalty", "")
        score_str = f"{hs}–{as_}"
        if hp and ap:
            score_str += f" (pen {hp}–{ap})"

        round_lbl = _ROUND_LABEL.get(row["Round"], row["Round"])

        def _merge_goals(regular: str, penalty: str) -> str:
            """Combine regular goals and penalty goals into one pipe-separated string."""
            parts = [g for g in (regular or "").split("|") if g.strip()]
            for g in (penalty or "").split("|"):
                g = g.strip()
                if g:
                    parts.append(g)  # already contains "(P)" in the source data
            # Sort by minute if possible
            def _minute(s: str) -> int:
                m = re.search(r"(\d+)", s.split("·")[-1] if "·" in s else "")
                return int(m.group(1)) if m else 999
            parts.sort(key=_minute)
            return "|".join(parts)

        return {
            "match_id":      f"hist_{row['Year']}_{row['Date']}_{hc}_{ac}",
            "home":          hc or row["home_team"],
            "away":          ac or row["away_team"],
            "stage":         "historical",
            "stage_label":   f"{row['Year']} · {round_lbl}",
            "kickoff_local": row.get("Date", ""),
            "venue":         row.get("Venue", ""),
            "historical":    True,
            "year":          row["Year"],
            "round":         round_lbl,
            "result":        score_str,
            "home_goals":    _merge_goals(row.get("home_goal",""), row.get("home_penalty_goal","")),
            "away_goals":    _merge_goals(row.get("away_goal",""), row.get("away_penalty_goal","")),
            "raw":           _extract_features(row, profile),
            "reasons":       {},
        }

    return [{"match_a": _info(a), "match_b": _info(b)} for a, b in pairs]
