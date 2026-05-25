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
    # Current / recent
    "Argentina":      "ARG", "Brazil":         "BRA", "France":      "FRA",
    "Germany":        "GER", "Spain":          "ESP", "England":     "ENG",
    "Portugal":       "POR", "Netherlands":    "NED", "Uruguay":     "URU",
    "Colombia":       "COL", "Morocco":        "MAR", "United States": "USA",
    "Croatia":        "CRO", "Switzerland":    "SUI", "Belgium":     "BEL",
    "Japan":          "JPN", "Korea Republic": "KOR", "Australia":   "AUS",
    "Canada":         "CAN", "Ecuador":        "ECU", "Senegal":     "SEN",
    "Ghana":          "GHA", "Nigeria":        "NGA", "Cameroon":    "CMR",
    "Egypt":          "EGY", "Mexico":         "MEX", "Poland":      "POL",
    "Denmark":        "DEN", "Serbia":         "SRB", "Sweden":      "SWE",
    "Iceland":        "ISL", "Russia":         "RUS", "Peru":        "PER",
    "Panama":         "PAN", "Tunisia":        "TUN", "Costa Rica":  "CRC",
    "Wales":          "WAL", "Qatar":          "QAT", "Saudi Arabia": "KSA",
    "IR Iran":        "IRN", "Ivory Coast":    "CIV", "Algeria":     "ALG",
    "Austria":        "AUT", "Norway":         "NOR", "Scotland":    "SCO",
    "Jordan":         "JOR", "Uzbekistan":     "UZB", "Curacao":     "CUR",
    "Paraguay":       "PAR", "Bosnia and Herzegovina": "BIH",
    "Turkey":         "TUR", "Czech Republic": "CZE",
    "Cape Verde":     "CPV", "DR Congo":       "COD",
    # 2010 / 2014 additions
    "Chile":              "CHI", "Côte d'Ivoire":      "CIV",
    "Greece":             "GRE", "Honduras":           "HON",
    "Italy":              "ITA", "Korea DPR":          "PRK",
    "New Zealand":        "NZL", "Slovakia":           "SVK",
    "Slovenia":           "SVN", "South Africa":       "RSA",
    # 2006 additions
    "Angola":             "ANG", "Serbia and Montenegro": "SCG",
    "Togo":               "TOG", "Trinidad and Tobago":   "TRI",
    "Ukraine":            "UKR",
    # Historical (pre-2006) — enables full 1930-2022 coverage
    "Bolivia":            "BOL", "Bulgaria":            "BUL",
    "China PR":           "CHN", "Cuba":                "CUB",
    "Czechoslovakia":     "TCH", "Dutch East Indies":   "DEI",
    "El Salvador":        "SLV", "FR Yugoslavia":       "YUG",
    "Germany DR":         "GDR", "Haiti":               "HAI",
    "Hungary":            "HUN", "Iraq":                "IRQ",
    "Israel":             "ISR", "Jamaica":             "JAM",
    "Kuwait":             "KUW", "Northern Ireland":    "NIR",
    "Republic of Ireland":"IRL", "Romania":             "ROU",
    "Soviet Union":       "URS", "Türkiye":             "TUR",
    "United Arab Emirates":"UAE","West Germany":        "GER",
    "Yugoslavia":         "YUG", "Zaire":               "COD",
}


def name_to_code(name: str) -> str | None:
    return _NAME_TO_CODE.get(name)


# ── Stage → raw score ─────────────────────────────────────────────────────────

_ROUND_RAW: dict[str, float] = {
    "Group stage":          0.25,
    "First round":          0.25,
    "First group stage":    0.25,
    "Group stage play-off": 0.35,
    "Second round":         0.40,
    "Second group stage":   0.40,
    "Round of 16":          0.55,
    "Quarter-finals":       0.75,
    "Semi-finals":          0.90,
    "Third-place match":    0.60,
    "Final stage":          0.85,
    "Final":                1.00,
}

_ROUND_LABEL: dict[str, str] = {
    "Group stage":          "Fase de grupos",
    "First round":          "Primera ronda",
    "First group stage":    "Primera fase de grupos",
    "Group stage play-off": "Desempate de grupo",
    "Second round":         "Segunda ronda",
    "Second group stage":   "Segunda fase de grupos",
    "Round of 16":          "16avos",
    "Quarter-finals":       "Cuartos",
    "Semi-finals":          "Semifinal",
    "Third-place match":    "3er lugar",
    "Final stage":          "Ronda final",
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
def _wc_drama() -> dict[frozenset, float]:
    try:
        from db.query import wc_drama_scores
        return wc_drama_scores()
    except Exception:
        return {}

@lru_cache(maxsize=1)
def _all_h2h() -> dict[frozenset, float]:
    try:
        from db.query import all_h2h_scores
        return all_h2h_scores()
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


@lru_cache(maxsize=1)
def _team_era_stars() -> dict[tuple[str, int], float]:
    """Returns {(fifa_code, wc_year): top_star_tier} from transfermarkt data."""
    try:
        from db.query import team_era_star_power
        return team_era_star_power()
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _star_name_lookup() -> dict[str, float]:
    """Returns {normalized_name: star_tier} for individual player matching."""
    try:
        from db.query import historical_star_lookup
        return historical_star_lookup()
    except Exception:
        return {}


def _star_power_raw(
    home_code: str | None,
    away_code: str | None,
    wc_year: int | None = None,
) -> float:
    """
    Star power for a historical match using transfermarkt national team data.
    Uses team-era lookup (best star tier per team at given WC year).
    Falls back to FC26 ratings for 2026 matches.
    """
    era_stars = _team_era_stars()

    # Snap to nearest WC year
    if wc_year and wc_year >= 1930:
        yr = wc_year
    else:
        yr = 2022  # fallback

    s_home = era_stars.get((home_code, yr), 0.0) if home_code else 0.0
    s_away = era_stars.get((away_code, yr), 0.0) if away_code else 0.0

    if s_home == 0.0 and s_away == 0.0:
        return 0.0
    return (s_home + s_away) / 2.0


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

def _parse_match_date(row: dict) -> "date | None":
    from datetime import date
    try:
        return date.fromisoformat(row.get("Date", ""))
    except (ValueError, TypeError):
        return None


def _parse_goal_minutes(goal_str: str) -> list[int]:
    """Parse 'Name · minute|Name · minute' → [int, ...] list of minutes."""
    minutes = []
    for part in (goal_str or "").split("|"):
        m = re.search(r'·\s*(\d+)', part)
        if m:
            minutes.append(int(m.group(1)))
    return minutes


def _chaos_raw(row: dict) -> float:
    """
    Enhanced chaos score using actual match events:
    - Total goals (weight 0.40)
    - Late goals 75+ min (weight 0.30)
    - Red cards (weight 0.15)
    - Penalty shootout (weight 0.15)
    """
    try:
        hs = int(float(row.get("home_score", 0) or 0))
        as_ = int(float(row.get("away_score", 0) or 0))
        total_goals = hs + as_
    except (ValueError, TypeError):
        total_goals = 0

    home_mins = _parse_goal_minutes(row.get("home_goal", ""))
    away_mins = _parse_goal_minutes(row.get("away_goal", ""))
    late_goals = sum(1 for m in home_mins + away_mins if m >= 75)

    red_cards = bool(row.get("home_red_card", "")) or bool(row.get("away_red_card", ""))
    penalty_so = bool(row.get("home_penalty", ""))

    goal_c  = min(1.0, total_goals / 5.0)
    late_c  = min(1.0, late_goals / 2.0)
    card_c  = 1.0 if red_cards else 0.0
    pen_c   = 1.0 if penalty_so else 0.0

    return min(1.0, goal_c * 0.40 + late_c * 0.30 + card_c * 0.15 + pen_c * 0.15)


def _elo_competitive_tension(home_code: str | None, away_code: str | None, match_date: "date | None") -> float:
    """Competitive Tension: entropy^0.7 * (0.4 + 0.6 * prestige). Mirrors CompetitiveTensionScorer."""
    if not home_code or not away_code:
        return 0.5
    import math
    from classifier.elo import win_probability, elo_at_date
    p_h, p_d, p_a = win_probability(home_code, away_code, as_of=match_date, neutral=True)
    H = -sum(p * math.log(p) for p in (p_h, p_d, p_a) if p > 0)
    entropy = H / math.log(3)
    avg_elo = (elo_at_date(home_code, match_date) + elo_at_date(away_code, match_date)) / 2
    prestige = max(0.0, min(1.0, (avg_elo - 1400) / 700))
    return min(1.0, (entropy ** 0.7) * (0.4 + 0.6 * prestige))


def _elo_upset(home_code: str | None, away_code: str | None, match_date: "date | None") -> float:
    """Upset Potential: gap × threat. Mirrors UpsetPotentialScorer."""
    if not home_code or not away_code:
        return 0.5
    from classifier.elo import win_probability, elo_at_date
    p_home, _, p_away = win_probability(home_code, away_code, as_of=match_date, neutral=True)
    elo_h = elo_at_date(home_code, match_date)
    elo_a = elo_at_date(away_code, match_date)
    gap = min(1.0, abs(elo_h - elo_a) / 400.0)
    total_dec = p_home + p_away
    p_under = min(p_home, p_away) / total_dec if total_dec > 0 else 0.5
    threat = min(1.0, p_under / 0.30)
    return min(1.0, gap * threat * 4.0)


def _elo_form(home_code: str | None, away_code: str | None, match_date: "date | None") -> float:
    """ELO momentum for both teams up to match date, weighted toward hotter team."""
    from classifier.elo import form_delta
    known = [(c, form_delta(c, as_of=match_date)) for c in (home_code, away_code) if c]
    if not known:
        return 0.5
    vals = [(delta + 1.0) / 2.0 for _, delta in known]
    return (sum(vals) + max(vals)) / (len(vals) + 1)


def _extract_features(row: dict, profile: UserProfile) -> dict[str, float]:
    home_code = name_to_code(row["home_team"])
    away_code = name_to_code(row["away_team"])
    affs = profile.team_affinities

    match_date = _parse_match_date(row)

    # Favorite Team
    fav_team_raw = max(affs.get(home_code or "", 0.0), affs.get(away_code or "", 0.0))

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
        getattr(profile, "favorite_players", []),
    )

    # Competitive Tension: entropy × prestige (pre-match ELO)
    competitive_tension_raw = _elo_competitive_tension(home_code, away_code, match_date)

    # Chaos Potential: enhanced score using match events
    goal_fest_raw = _chaos_raw(row)

    # Upset Potential: pre-match ELO probability gap
    upset_raw = _elo_upset(home_code, away_code, match_date)

    # Narrative: WC meetings + rivalry + drama + all-competition H2H
    # (mirrors NarrativeScorer.score formula)
    pair       = frozenset({home_code, away_code}) if home_code and away_code else frozenset()
    n_meetings = _wc_meetings().get(pair, 0)
    drama      = _wc_drama().get(pair, 0.0)
    all_h2h    = _all_h2h().get(pair, 0.0)

    def _meetings_score(n: int) -> float:
        if n == 0:  return 0.0
        if n <= 2:  return 0.45
        if n <= 4:  return 0.65
        if n <= 6:  return 0.85
        return 1.0

    wc_combined    = max(_meetings_score(n_meetings), rivalry_raw)
    narrative_raw  = min(1.0, 0.50 * wc_combined + 0.20 * drama + 0.30 * all_h2h)

    # Form: ELO momentum up to match date
    form_raw = _elo_form(home_code, away_code, match_date)

    return {
        "Favorite Team":        fav_team_raw,
        "Match Stage":          stage_raw,
        "Competitive Tension":  competitive_tension_raw,
        "Chaos Potential":      goal_fest_raw,
        "Favorite Player":      0.0,   # neutral: historical goal-scorer matching is too noisy for learning
        "Upset Potential":      upset_raw,
        "Form":                 form_raw,
        "Star Power":           _star_power_raw(home_code, away_code, int(row.get("Year", 0) or 0)),
        "Narrative":            narrative_raw,
        "Same Group":           0.0,   # neutral: no real "same group" context in historical matches
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
        years = list(range(1930, 2023, 4))  # all World Cups 1930-2022

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
    favs      = {t for t, a in profile.team_affinities.items() if a > 0}
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


def _match_id(row: dict) -> str:
    hc = name_to_code(row["home_team"]) or row["home_team"]
    ac = name_to_code(row["away_team"]) or row["away_team"]
    return f"hist_{row['Year']}_{row['Date']}_{hc}_{ac}"


def _match_info(row: dict, profile: UserProfile) -> dict:
    hc  = name_to_code(row["home_team"])
    ac  = name_to_code(row["away_team"])
    hs  = row.get("home_score", "?")
    as_ = row.get("away_score", "?")
    hp  = row.get("home_penalty", "")
    ap  = row.get("away_penalty", "")
    score_str = f"{hs}–{as_}"
    if hp and ap:
        score_str += f" (pen {hp}–{ap})"

    round_lbl = _ROUND_LABEL.get(row["Round"], row["Round"])

    def _merge_goals(regular: str, penalty: str) -> str:
        parts = [g for g in (regular or "").split("|") if g.strip()]
        for g in (penalty or "").split("|"):
            g = g.strip()
            if g:
                parts.append(g)
        def _minute(s: str) -> int:
            m = re.search(r"(\d+)", s.split("·")[-1] if "·" in s else "")
            return int(m.group(1)) if m else 999
        parts.sort(key=_minute)
        return "|".join(parts)

    return {
        "match_id":      _match_id(row),
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
        "home_goals":    _merge_goals(row.get("home_goal", ""), row.get("home_penalty_goal", "")),
        "away_goals":    _merge_goals(row.get("away_goal", ""), row.get("away_penalty_goal", "")),
        "raw":           _extract_features(row, profile),
    }


def _feature_spread(feats: dict[str, float]) -> float:
    """Standard deviation of feature values — higher = more informative."""
    vals = list(feats.values())
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5


def _dominant_feature(feats: dict[str, float]) -> str:
    """Which scorer has the highest raw value in this match."""
    return max(feats, key=feats.get)


def _diagnostic_score(feature_idx: int, vec: list[float]) -> float:
    """
    How diagnostic a match is for a specific scorer.
    High when that scorer is high AND others are low.
    """
    val = vec[feature_idx]
    if val < 0.20:
        return 0.0
    others = [v for i, v in enumerate(vec) if i != feature_idx]
    others_mean = sum(others) / len(others) if others else 0.0
    return val * val / (others_mean + 0.05)


def sample_historical_matches(
    profile: UserProfile,
    n: int = 15,
    years: list[int] | None = None,
    seed: int | None = None,
    exclude_ids: list[str] | None = None,
    rated_examples: list[dict] | None = None,
) -> list[dict]:
    """
    Return n individual historical WC matches for single-match rating.

    Uses a hybrid strategy:
      1. If rated_examples exist → active learning: pick matches where the
         current Ridge model has highest prediction uncertainty (bootstrap std).
         These are the matches whose rating will maximally reduce model error.
      2. Diagnostic core: one match per scorer where that dimension dominates,
         so each rating isolates preference for one scorer.
      3. Fill remaining slots with diverse, high-spread matches.
      4. Randomize presentation order.

    Active learning means users reach good personalization in ~10 ratings
    instead of ~30.
    """
    if years is None:
        years = list(range(1930, 2023, 4))  # all World Cups 1930-2022

    excluded   = set(exclude_ids or [])
    year_set   = {str(y) for y in years}
    history    = _load_history()
    candidates = [
        r for r in history
        if r["Year"] in year_set
        and r["home_score"] not in ("", "NA")
        and r["away_score"] not in ("", "NA")
        and name_to_code(r["home_team"]) is not None
        and name_to_code(r["away_team"]) is not None
        and _match_id(r) not in excluded
    ]

    if not candidates:
        return []

    rng  = random.Random(seed)
    favs = {t for t, a in profile.team_affinities.items() if a > 0}
    from classifier.learning import SCORER_NAMES, predict_uncertainty

    # ── Step 1: extract features for all candidates ──────────────────────
    enriched: list[tuple[dict, dict[str, float], list[float]]] = []
    for r in candidates:
        feats = _extract_features(r, profile)
        vec   = [feats[s] for s in SCORER_NAMES]
        enriched.append((r, feats, vec))

    selected: list[tuple[dict, dict[str, float]]] = []
    seen_ids: set[str] = set()

    # ── Step 2: active learning — pick most uncertain matches ────────────
    # If we have prior ratings, use bootstrap uncertainty to find matches
    # where the model disagrees most → rating these reduces error fastest.
    if rated_examples and len(rated_examples) >= 5:
        candidate_raws = [feats for _, feats, _ in enriched]
        uncertainties = predict_uncertainty(rated_examples, candidate_raws)

        # Rank by uncertainty, pick top matches
        scored = list(zip(uncertainties, range(len(enriched))))
        scored.sort(reverse=True)

        n_active = min(n // 2, len(scored))  # half from active learning
        for _, idx in scored[:n_active]:
            r, feats, vec = enriched[idx]
            mid = _match_id(r)
            if mid not in seen_ids:
                seen_ids.add(mid)
                selected.append((r, feats))

    # ── Step 3: diagnostic core — best isolating match per scorer ────────
    for i, scorer in enumerate(SCORER_NAMES):
        if len(selected) >= n:
            break

        best_e    = None
        best_diag = -1.0
        for r, feats, vec in enriched:
            mid = _match_id(r)
            if mid in seen_ids:
                continue
            diag = _diagnostic_score(i, vec)
            hc = name_to_code(r["home_team"])
            ac = name_to_code(r["away_team"])
            if hc in favs or ac in favs:
                diag *= 1.3
            if diag > best_diag:
                best_diag = diag
                best_e    = (r, feats)

        if best_e:
            seen_ids.add(_match_id(best_e[0]))
            selected.append(best_e)

    # ── Step 4: fill remaining slots with diverse matches ────────────────
    def _fill_key(e):
        r, feats, vec = e
        spread = _feature_spread(feats)
        hc = name_to_code(r["home_team"])
        ac = name_to_code(r["away_team"])
        is_fav  = hc in favs or ac in favs
        is_late = _ROUND_RAW.get(r["Round"], 0) >= 0.75
        return (-int(is_fav), -int(is_late), -spread)

    remaining = [e for e in enriched if _match_id(e[0]) not in seen_ids]
    rng.shuffle(remaining)
    remaining.sort(key=_fill_key)

    for r, feats, vec in remaining:
        if len(selected) >= n:
            break
        mid = _match_id(r)
        if mid not in seen_ids:
            seen_ids.add(mid)
            selected.append((r, feats))

    rng.shuffle(selected)  # randomize presentation order
    return [_match_info(r, profile) for r, _ in selected]
