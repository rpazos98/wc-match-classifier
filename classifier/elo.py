"""
ELO rating engine for international football.

Computes time-series ELO ratings from data/intl_results/results.csv
(49K+ completed matches, 1872–2026).

K-factors by tournament weight:
  32 — FIFA World Cup
  28 — Continental championships (Copa América, UEFA Euro, AFCON, etc.)
  25 — World Cup qualification
  22 — Continental qualification
  20 — Other competitive
  10 — Friendly

Home advantage: +100 ELO points when match is not neutral.
Starting ELO: 1500 for all teams.

Public API accepts FIFA codes (e.g. "ARG") which are translated
internally to the canonical team name used in the CSV.
"""
from __future__ import annotations

import csv
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

_DATA     = Path(__file__).parent.parent / "data" / "intl_results" / "results.csv"
_HOME_ADV = 100.0
_START    = 1500.0
_SCALE    = 400.0

# FIFA code → team name as it appears in intl_results/results.csv
_CODE_TO_CSV: dict[str, str] = {
    "ARG": "Argentina",       "BRA": "Brazil",          "FRA": "France",
    "GER": "Germany",         "ESP": "Spain",            "ENG": "England",
    "POR": "Portugal",        "NED": "Netherlands",      "URU": "Uruguay",
    "COL": "Colombia",        "MAR": "Morocco",          "USA": "United States",
    "CRO": "Croatia",         "SUI": "Switzerland",      "BEL": "Belgium",
    "JPN": "Japan",           "KOR": "South Korea",      "AUS": "Australia",
    "CAN": "Canada",          "ECU": "Ecuador",          "SEN": "Senegal",
    "GHA": "Ghana",           "NGA": "Nigeria",          "CMR": "Cameroon",
    "EGY": "Egypt",           "MEX": "Mexico",           "POL": "Poland",
    "DEN": "Denmark",         "SRB": "Serbia",           "SWE": "Sweden",
    "ISL": "Iceland",         "RUS": "Russia",           "PER": "Peru",
    "PAN": "Panama",          "TUN": "Tunisia",          "CRC": "Costa Rica",
    "WAL": "Wales",           "QAT": "Qatar",            "KSA": "Saudi Arabia",
    "IRN": "Iran",            "CIV": "Ivory Coast",      "ALG": "Algeria",
    "AUT": "Austria",         "NOR": "Norway",           "SCO": "Scotland",
    "JOR": "Jordan",          "UZB": "Uzbekistan",       "CUR": "Curaçao",
    "PAR": "Paraguay",        "BIH": "Bosnia and Herzegovina",
    "TUR": "Turkey",          "CZE": "Czech Republic",   "CPV": "Cape Verde",
    "COD": "DR Congo",        "IRQ": "Iraq",             "ITA": "Italy",
    "RSA": "South Africa",    "NZL": "New Zealand",      "HAI": "Haiti",
    "CHI": "Chile",           "GRE": "Greece",           "HON": "Honduras",
    "SVK": "Slovakia",        "SVN": "Slovenia",         "UKR": "Ukraine",
}


def _k_factor(tournament: str) -> float:
    t = tournament.lower()
    if "world cup" in t and "qualif" not in t and "qualifier" not in t:
        return 32.0
    if any(x in t for x in (
        "copa america", "uefa euro", "european championship",
        "african cup of nations", "afcon", "asian cup",
        "gold cup", "copa oro", "nations league", "nations cup",
        "concacaf championship",
    )):
        return 28.0 if ("qualif" not in t and "qualifier" not in t) else 22.0
    if "qualif" in t or "qualifier" in t:
        return 25.0
    if "friendly" in t:
        return 10.0
    return 20.0


@lru_cache(maxsize=1)
def _build_history() -> dict[str, list[tuple[date, float]]]:
    """
    Returns {csv_team_name: [(match_date, elo_after_match), ...]} sorted ascending.
    Only processes completed matches (scores not NA/empty).
    """
    ratings: dict[str, float] = {}
    history: dict[str, list[tuple[date, float]]] = {}

    with open(_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Sort chronologically for correct sequential ELO update
    rows.sort(key=lambda r: r["date"])

    for row in rows:
        home = row["home_team"]
        away = row["away_team"]

        try:
            hs  = int(float(row["home_score"]))
            as_ = int(float(row["away_score"]))
        except (ValueError, TypeError):
            continue  # skip matches with NA/missing scores

        try:
            d = date.fromisoformat(row["date"])
        except ValueError:
            continue

        neutral = row.get("neutral", "FALSE").strip().upper() == "TRUE"

        r_home = ratings.get(home, _START)
        r_away = ratings.get(away, _START)

        # Effective rating includes home advantage if not neutral ground
        r_home_eff = r_home + (0.0 if neutral else _HOME_ADV)

        exp_home = 1.0 / (1.0 + 10.0 ** ((r_away - r_home_eff) / _SCALE))

        if hs > as_:
            act_home, act_away = 1.0, 0.0
        elif hs < as_:
            act_home, act_away = 0.0, 1.0
        else:
            act_home, act_away = 0.5, 0.5

        k = _k_factor(row.get("tournament", ""))

        ratings[home] = r_home + k * (act_home - exp_home)
        ratings[away] = r_away + k * (act_away - (1.0 - exp_home))

        history.setdefault(home, []).append((d, ratings[home]))
        history.setdefault(away, []).append((d, ratings[away]))

    return history


@lru_cache(maxsize=1)
def _latest_ratings() -> dict[str, float]:
    """Most recent ELO for every team (by CSV name)."""
    return {team: entries[-1][1] for team, entries in _build_history().items()}


def _resolve(code_or_name: str) -> str:
    """Translate FIFA code to CSV name; falls back to the input unchanged."""
    return _CODE_TO_CSV.get(code_or_name, code_or_name)


def elo_at_date(code_or_name: str, as_of: date) -> float:
    """
    ELO for a team at a specific date (last rating on or before that date).
    Accepts FIFA code ("ARG") or CSV name ("Argentina").
    Returns 1500.0 if no history found.
    """
    name    = _resolve(code_or_name)
    entries = _build_history().get(name)
    if not entries:
        return _START

    # Binary search: find last entry with date <= as_of
    lo, hi, result = 0, len(entries) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if entries[mid][0] <= as_of:
            result = entries[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return result if result is not None else _START


def current_elo(code_or_name: str) -> float:
    """Most recent ELO rating. Accepts FIFA code or CSV name. Returns 1500.0 if unknown."""
    name = _resolve(code_or_name)
    return _latest_ratings().get(name, _START)


def win_probability(
    home: str,
    away: str,
    as_of: date | None = None,
    neutral: bool = True,
) -> tuple[float, float, float]:
    """
    Returns (p_home_win, p_draw, p_away_win) for a match.

    Both `home` and `away` accept FIFA codes or CSV names.
    If `as_of` is None, uses current (most recent) ratings.

    Draw probability modelled as:
      p_draw ≈ 0.28 * exp(-((elo_diff / 200)²))
    which peaks at 0.28 when teams are equal and decays symmetrically.
    """
    if as_of is not None:
        r_home = elo_at_date(home, as_of)
        r_away = elo_at_date(away, as_of)
    else:
        r_home = current_elo(home)
        r_away = current_elo(away)

    r_home_eff = r_home + (0.0 if neutral else _HOME_ADV)
    exp_home   = 1.0 / (1.0 + 10.0 ** ((r_away - r_home_eff) / _SCALE))

    diff   = abs(r_home_eff - r_away)
    p_draw = 0.28 * math.exp(-((diff / 200.0) ** 2))

    p_decisive = 1.0 - p_draw
    p_home     = exp_home * p_decisive
    p_away     = (1.0 - exp_home) * p_decisive

    return p_home, p_draw, p_away


def form_delta(
    code_or_name: str,
    as_of: date | None = None,
    n: int = 8,
) -> float:
    """
    ELO change over the last `n` matches (up to `as_of` if given).
    Returns value in [-1.0, 1.0], normalised over a 200-point window.
    0.0 means no change; positive = improving; negative = declining.
    """
    name    = _resolve(code_or_name)
    entries = _build_history().get(name, [])

    if len(entries) < 2:
        return 0.0

    window = entries if as_of is None else [e for e in entries if e[0] <= as_of]
    if len(window) < 2:
        return 0.0

    recent = window[-n:]
    delta  = recent[-1][1] - recent[0][1]
    return max(-1.0, min(1.0, delta / 200.0))


def top_elo_teams(n: int = 20) -> list[tuple[str, float]]:
    """Returns [(csv_name, elo), ...] sorted descending by current ELO. Useful for debugging."""
    ratings = _latest_ratings()
    return sorted(ratings.items(), key=lambda x: x[1], reverse=True)[:n]