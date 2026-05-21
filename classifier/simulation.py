"""
WC 2026 bracket simulation — bracket sourced from FIFA2026_schedule_Fixtures.csv.

R32 slot assignments (matches 73–88):
  73: RU_A   vs RU_B
  74: W_E    vs T3(A/B/C/D/F)
  75: W_F    vs RU_C
  76: W_C    vs RU_F
  77: W_I    vs T3(C/D/F/G/H)
  78: RU_E   vs RU_I
  79: W_A    vs T3(C/E/F/H/I)
  80: W_L    vs T3(E/H/I/J/K)
  81: W_D    vs T3(B/E/F/I/J)
  82: W_G    vs T3(A/E/H/I/J)
  83: RU_K   vs RU_L
  84: W_H    vs RU_J
  85: W_B    vs T3(E/F/G/I/J)
  86: W_J    vs RU_H
  87: W_K    vs T3(D/E/I/J/L)
  88: RU_D   vs RU_G

R16 feeds (matches 89–96):
  89: W73  vs W74    90: W75  vs W76    91: W77  vs W78    92: W79  vs W80
  93: W83  vs W84    94: W81  vs W82    95: W86  vs W88    96: W85  vs W87

QF feeds (matches 97–100):
  97: W89 vs W90    98: W93 vs W94    99: W91 vs W92   100: W95 vs W96

SF feeds (matches 101–102):
  101: W97 vs W98    102: W99 vs W100

3rd/Final:
  103: L101 vs L102    104: W101 vs W102
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, replace

from .models import Match, Stage


@dataclass
class SimulationResult:
    matches:       list[Match]
    standings:     dict[str, list[dict]]  # group_letter → [{team, pts, gd}, ...]
    match_winners: dict[int, str]         # match_number → winner code
    match_losers:  dict[int, str]         # match_number → loser code


@dataclass
class MonteCarloResult:
    n_sims:                  int
    champion_counts:         dict[str, int]              # team → times won final
    finalist_counts:         dict[str, int]              # team → times reached final
    semifinal_counts:        dict[str, int]              # team → times reached SF
    match_winner_counts:     dict[int, dict[str, int]]   # match_num → team → wins
    match_participant_counts: dict[int, dict[str, int]]  # match_num → team → appearances
    consensus:               SimulationResult             # single rep bracket

# ── Real bracket definitions ───────────────────────────────────────────────────

# Which group position occupies each side of every R32 match
# Entries: ("W"|"RU", group_letter) or ("T3", frozenset_of_allowed_groups)
_R32_SLOTS: dict[int, tuple] = {
    73: (("RU", "A"), ("RU", "B")),
    74: (("W",  "E"), ("T3", frozenset("ABCDF"))),
    75: (("W",  "F"), ("RU", "C")),
    76: (("W",  "C"), ("RU", "F")),
    77: (("W",  "I"), ("T3", frozenset("CDFGH"))),
    78: (("RU", "E"), ("RU", "I")),
    79: (("W",  "A"), ("T3", frozenset("CEFHI"))),
    80: (("W",  "L"), ("T3", frozenset("EHIJK"))),
    81: (("W",  "D"), ("T3", frozenset("BEFIJ"))),
    82: (("W",  "G"), ("T3", frozenset("AEHIJ"))),
    83: (("RU", "K"), ("RU", "L")),
    84: (("W",  "H"), ("RU", "J")),
    85: (("W",  "B"), ("T3", frozenset("EFGIJ"))),
    86: (("W",  "J"), ("RU", "H")),
    87: (("W",  "K"), ("T3", frozenset("DEIJL"))),
    88: (("RU", "D"), ("RU", "G")),
}

_R16_FEEDS: dict[int, tuple[int, int]] = {
    89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
}
_QF_FEEDS: dict[int, tuple[int, int]] = {
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
}
_SF_FEEDS: dict[int, tuple[int, int]] = {
    101: (97, 98), 102: (99, 100),
}

# T3 slot match numbers that need a third-place team
_T3_SLOT_MATCH_NUMS = {74, 77, 79, 80, 81, 82, 85, 87}


# ── Public API ─────────────────────────────────────────────────────────────────

def simulate_bracket(
    matches: list[Match],
    seed: int | None = None,
    quality: dict[str, float] | None = None,
) -> SimulationResult:
    """
    Return a SimulationResult with all TBD teams resolved via simulation.
    Group stage matches are kept unchanged; knockout teams are filled in.
    Pass `quality` to avoid repeated DB lookups in Monte Carlo runs.
    """
    rng = random.Random(seed)

    if quality is None:
        from db.query import team_quality_scores
        quality = team_quality_scores()

    group_matches = [m for m in matches if m.stage == Stage.GROUP]
    knockout      = {m.match_id: m for m in matches if m.stage != Stage.GROUP}

    # Step 1 – simulate group stage → standings + per-match winners
    standings, group_match_winners = _simulate_groups(group_matches, quality, rng)

    # Step 2 – extract positions
    group_winners:  dict[str, str] = {}
    group_runners:  dict[str, str] = {}
    group_thirds_q: list[dict]     = []  # sorted candidates for T3 slot assignment

    for grp, table in standings.items():
        group_winners[grp] = table[0]["team"]
        group_runners[grp] = table[1]["team"]
        third = table[2]
        group_thirds_q.append({
            "team":  third["team"],
            "group": grp,
            "pts":   third["pts"],
            "gd":    third["gd"],
            "gf":    third["gf"],
        })

    # Sort T3 candidates best-first: pts → gd → gf (FIFA criteria)
    group_thirds_q.sort(key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)

    # Step 3 – resolve T3 slot assignments
    # For each T3 slot (match), pick the best available T3 team
    # whose group is in the slot's allowed set; fall back to best remaining.
    t3_assignments: dict[int, str] = {}
    available_t3   = list(group_thirds_q)  # mutable pool

    for match_num in sorted(_T3_SLOT_MATCH_NUMS):
        allowed = _R32_SLOTS[match_num][1][1]  # frozenset of allowed groups
        # Try to find best T3 from allowed groups
        pick = next(
            (t for t in available_t3 if t["group"] in allowed),
            available_t3[0] if available_t3 else None,
        )
        if pick:
            t3_assignments[match_num] = pick["team"]
            available_t3.remove(pick)

    # Step 4 – simulate knockout rounds
    winners: dict[int, str] = dict(group_match_winners)  # seed with group results
    losers:  dict[int, str] = {}
    resolved: list[Match]   = []

    def _team_for_slot(slot: tuple) -> str:
        kind, val = slot
        if kind == "W":
            return group_winners.get(val, "TBD")
        if kind == "RU":
            return group_runners.get(val, "TBD")
        return "TBD"  # T3 handled separately

    def _resolve(match_num: int, home: str, away: str) -> None:
        mid = f"M{match_num:03d}"
        m   = knockout[mid]
        resolved.append(replace(m, home=home, away=away))
        w, l = _sim_ko(home, away, quality, rng)
        winners[match_num] = w
        losers[match_num]  = l

    # R32
    for mn, (slot_h, slot_a) in _R32_SLOTS.items():
        home = _team_for_slot(slot_h)
        if slot_h[0] == "T3":
            home = t3_assignments.get(mn, "TBD")
        away = _team_for_slot(slot_a)
        if slot_a[0] == "T3":
            away = t3_assignments.get(mn, "TBD")
        _resolve(mn, home, away)

    # R16
    for mn, (a, b) in _R16_FEEDS.items():
        _resolve(mn, winners[a], winners[b])

    # QF
    for mn, (a, b) in _QF_FEEDS.items():
        _resolve(mn, winners[a], winners[b])

    # SF
    for mn, (a, b) in _SF_FEEDS.items():
        _resolve(mn, winners[a], winners[b])

    # 3rd place
    _resolve(103, losers[101], losers[102])

    # Final
    _resolve(104, winners[101], winners[102])

    return SimulationResult(
        matches       = group_matches + resolved,
        standings     = standings,
        match_winners = winners,
        match_losers  = losers,
    )


def run_monte_carlo(
    matches: list[Match],
    n: int = 1000,
    seed: int | None = None,
) -> MonteCarloResult:
    """
    Run `n` independent simulations and aggregate win probabilities.
    Returns a MonteCarloResult with counts and a consensus bracket.
    """
    from db.query import team_quality_scores
    quality = team_quality_scores()

    rng = random.Random(seed)
    seeds = [rng.randint(0, 10**9) for _ in range(n)]

    champion_counts:          dict[str, int]              = defaultdict(int)
    finalist_counts:          dict[str, int]              = defaultdict(int)
    semifinal_counts:         dict[str, int]              = defaultdict(int)
    match_winner_counts:      dict[int, dict[str, int]]   = defaultdict(lambda: defaultdict(int))
    match_participant_counts: dict[int, dict[str, int]]   = defaultdict(lambda: defaultdict(int))

    for s in seeds:
        result = simulate_bracket(matches, seed=s, quality=quality)
        champion_counts[result.match_winners[104]] += 1
        finalist_counts[result.match_winners[104]] += 1
        finalist_counts[result.match_losers[104]]  += 1
        for mn in (101, 102):
            semifinal_counts[result.match_winners[mn]] += 1
            semifinal_counts[result.match_losers[mn]]  += 1
        for m in result.matches:
            if m.stage != Stage.GROUP:
                mn = int(m.match_id[1:])
                match_winner_counts[mn][result.match_winners.get(mn, m.home)] += 1
                match_participant_counts[mn][m.home] += 1
                match_participant_counts[mn][m.away] += 1

    consensus = simulate_bracket(matches, seed=seed, quality=quality)

    return MonteCarloResult(
        n_sims                   = n,
        champion_counts          = dict(champion_counts),
        finalist_counts          = dict(finalist_counts),
        semifinal_counts         = dict(semifinal_counts),
        match_winner_counts      = {mn: dict(t) for mn, t in match_winner_counts.items()},
        match_participant_counts = {mn: dict(t) for mn, t in match_participant_counts.items()},
        consensus                = consensus,
    )


# ── Simulation helpers ─────────────────────────────────────────────────────────

def _sim_ko(
    home: str,
    away: str,
    quality: dict[str, float],
    rng: random.Random,
) -> tuple[str, str]:
    """Simulate a knockout match → (winner, loser). No draws."""
    q_h = quality.get(home, 0.5)
    q_a = quality.get(away, 0.5)
    total = q_h + q_a
    return (home, away) if rng.random() < q_h / total else (away, home)


def _sim_score(q_winner: float, q_loser: float, rng: random.Random) -> tuple[int, int]:
    """Return (winner_goals, loser_goals). Winner always scores more."""
    base    = max(1, round(1.5 + q_winner * 1.5))   # quality → expected goals
    w_goals = rng.randint(base, base + 2)
    l_goals = rng.randint(0, max(0, w_goals - 1))
    return w_goals, l_goals


def _sim_draw_score(rng: random.Random) -> tuple[int, int]:
    """Return (goals, goals) for a draw."""
    g = rng.randint(0, 2)
    return g, g


def _simulate_groups(
    group_matches: list[Match],
    quality: dict[str, float],
    rng: random.Random,
) -> tuple[dict[str, list[dict]], dict[int, str]]:
    """
    Simulate all group stage matches.
    Returns ({group_letter: [{'team','pts','gd','gf'}, ...]}, {match_num: winner}).
    Standings sorted by pts → gd → gf (FIFA criteria 1-3 for best-third selection).
    """
    team_group = _load_team_groups()

    all_teams: dict[str, set[str]] = {}
    for m in group_matches:
        for t in (m.home, m.away):
            if t != "TBD":
                grp = team_group.get(t)
                if grp:
                    all_teams.setdefault(grp, set()).add(t)

    pts: dict[str, int] = {t: 0 for g in all_teams.values() for t in g}
    gd:  dict[str, int] = {t: 0 for g in all_teams.values() for t in g}
    gf:  dict[str, int] = {t: 0 for g in all_teams.values() for t in g}

    match_winners: dict[int, str] = {}
    draw_prob = 0.22
    for m in group_matches:
        if m.home == "TBD" or m.away == "TBD":
            continue
        q_h   = quality.get(m.home, 0.5)
        q_a   = quality.get(m.away, 0.5)
        total = q_h + q_a
        r     = rng.random()
        hw    = (1 - draw_prob) * q_h / total
        mn    = int(m.match_id[1:])
        if r < hw:
            hg, ag = _sim_score(q_h, q_a, rng)
            pts[m.home] += 3
            gf[m.home]  += hg;  gf[m.away]  += ag
            gd[m.home]  += hg - ag;  gd[m.away]  -= hg - ag
            match_winners[mn] = m.home
        elif r < hw + draw_prob:
            hg, ag = _sim_draw_score(rng)
            pts[m.home] += 1;  pts[m.away] += 1
            gf[m.home]  += hg;  gf[m.away]  += ag
            match_winners[mn] = m.home if q_h >= q_a else m.away
        else:
            ag, hg = _sim_score(q_a, q_h, rng)
            pts[m.away] += 3
            gf[m.home]  += hg;  gf[m.away]  += ag
            gd[m.away]  += ag - hg;  gd[m.home]  -= ag - hg
            match_winners[mn] = m.away

    standings: dict[str, list[dict]] = {}
    for grp, teams in all_teams.items():
        table = sorted(
            teams,
            key=lambda t: (pts[t], gd[t], gf[t]),
            reverse=True,
        )
        standings[grp] = [{"team": t, "pts": pts[t], "gd": gd[t], "gf": gf[t]} for t in table]

    return standings, match_winners


_team_group_cache: dict[str, str] = {}


def _load_team_groups() -> dict[str, str]:
    if not _team_group_cache:
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).parent.parent / "data" / "wc2026.db"
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT fifa_code, group_letter FROM teams WHERE is_placeholder = 0"
        ).fetchall()
        con.close()
        for code, grp in rows:
            if code and grp:
                _team_group_cache[code] = grp
    return _team_group_cache
