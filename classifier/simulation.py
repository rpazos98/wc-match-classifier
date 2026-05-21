"""
WC 2026 bracket simulation — bracket sourced from FIFA2026_schedule_Fixtures.csv.

R32 slot assignments (matches 73–88):
  73: 2A  vs 2B             74: 1C  vs 2F
  75: 1E  vs T3(A/B/C/D/F)  76: 1F  vs 2C
  77: 2E  vs 2I             78: 1I  vs T3(C/D/F/G/H)
  79: 1A  vs T3(C/E/F/H/I)  80: 1L  vs T3(E/H/I/J/K)
  81: 1G  vs T3(A/E/H/I/J)  82: 1D  vs T3(B/E/F/I/J)
  83: 1H  vs 2J             84: 2K  vs 2L
  85: 1B  vs T3(E/F/G/I/J)  86: 2D  vs 2G
  87: 1J  vs 2H             88: 1K  vs T3(D/E/I/J/L)

R16 feeds (matches 89–96):
  89: W73  vs W75    90: W74  vs W77    91: W76  vs W78    92: W79  vs W80
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
    standings:     dict[str, list[dict]]       # group_letter → [{team, pts, gd}, ...]
    match_winners: dict[int, str]              # match_number → winner code
    match_losers:  dict[int, str]              # match_number → loser code
    match_scores:  dict[int, tuple[int, int]]  # match_number → (home_goals, away_goals)


@dataclass
class MonteCarloResult:
    n_sims:                  int
    champion_counts:         dict[str, int]              # team → times won final
    finalist_counts:         dict[str, int]              # team → times reached final
    semifinal_counts:        dict[str, int]              # team → times reached SF
    match_winner_counts:     dict[int, dict[str, int]]   # match_num → team → wins
    match_participant_counts: dict[int, dict[str, int]]  # match_num → team → appearances
    representative:          SimulationResult             # most-aligned single run

# ── Real bracket definitions ───────────────────────────────────────────────────

# Which group position occupies each side of every R32 match
# Entries: ("W"|"RU", group_letter) or ("T3", frozenset_of_allowed_groups)
_R32_SLOTS: dict[int, tuple] = {
    73: (("RU", "A"), ("RU", "B")),
    74: (("W",  "C"), ("RU", "F")),
    75: (("W",  "E"), ("T3", frozenset("ABCDF"))),
    76: (("W",  "F"), ("RU", "C")),
    77: (("RU", "E"), ("RU", "I")),
    78: (("W",  "I"), ("T3", frozenset("CDFGH"))),
    79: (("W",  "A"), ("T3", frozenset("CEFHI"))),
    80: (("W",  "L"), ("T3", frozenset("EHIJK"))),
    81: (("W",  "G"), ("T3", frozenset("AEHIJ"))),
    82: (("W",  "D"), ("T3", frozenset("BEFIJ"))),
    83: (("W",  "H"), ("RU", "J")),
    84: (("RU", "K"), ("RU", "L")),
    85: (("W",  "B"), ("T3", frozenset("EFGIJ"))),
    86: (("RU", "D"), ("RU", "G")),
    87: (("W",  "J"), ("RU", "H")),
    88: (("W",  "K"), ("T3", frozenset("DEIJL"))),
}

_R16_FEEDS: dict[int, tuple[int, int]] = {
    89: (73, 75), 90: (74, 77), 91: (76, 78), 92: (79, 80),
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
}
_QF_FEEDS: dict[int, tuple[int, int]] = {
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
}
_SF_FEEDS: dict[int, tuple[int, int]] = {
    101: (97, 98), 102: (99, 100),
}

# T3 slot match numbers that need a third-place team
_T3_SLOT_MATCH_NUMS = {75, 78, 79, 80, 81, 82, 85, 88}


# ── ELO helpers ────────────────────────────────────────────────────────────────

def _elo_to_q(elo: float) -> float:
    """Map ELO to 0-1 quality scale. 1500→0.30, 1700→0.50, 2000→0.80."""
    return max(0.05, min(0.95, (elo - 1200) / 1000.0))


# ── Public API ─────────────────────────────────────────────────────────────────

def simulate_bracket(
    matches: list[Match],
    seed: int | None = None,
) -> SimulationResult:
    """
    Return a SimulationResult with all TBD teams resolved via simulation.
    Group stage matches are kept unchanged; knockout teams are filled in.
    """
    rng = random.Random(seed)

    group_matches = [m for m in matches if m.stage == Stage.GROUP]
    knockout      = {m.match_id: m for m in matches if m.stage != Stage.GROUP}

    # Load squads so knockout matches get squad data
    from db.query import _load_squads, _connect
    _sq_con = _connect()
    _squads = _load_squads(_sq_con)
    _sq_con.close()

    # Step 1 – simulate group stage → standings + per-match winners + scores
    standings, group_match_winners, group_match_scores = _simulate_groups(group_matches, rng)

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
    winners: dict[int, str]              = dict(group_match_winners)  # seed with group results
    losers:  dict[int, str]              = {}
    match_scores: dict[int, tuple[int, int]] = dict(group_match_scores)
    resolved: list[Match]                = []

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
        resolved.append(replace(m, home=home, away=away,
                                home_squad=_squads.get(home),
                                away_squad=_squads.get(away)))
        w, l, hg, ag = _sim_ko(home, away, rng)
        winners[match_num]     = w
        losers[match_num]      = l
        match_scores[match_num] = (hg, ag)

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
        match_scores  = match_scores,
    )


def run_monte_carlo(
    matches: list[Match],
    n: int = 1000,
    seed: int | None = None,
) -> MonteCarloResult:
    """
    Run `n` independent simulations and aggregate win probabilities.
    Returns a MonteCarloResult whose `representative` is the single run
    most aligned with the modal (most-frequent) winner of each KO match.
    """
    rng = random.Random(seed)
    seeds = [rng.randint(0, 10**9) for _ in range(n)]

    champion_counts:          dict[str, int]              = defaultdict(int)
    finalist_counts:          dict[str, int]              = defaultdict(int)
    semifinal_counts:         dict[str, int]              = defaultdict(int)
    match_winner_counts:      dict[int, dict[str, int]]   = defaultdict(lambda: defaultdict(int))
    match_participant_counts: dict[int, dict[str, int]]   = defaultdict(lambda: defaultdict(int))

    # Store lightweight per-run KO winners for representative selection
    run_ko_winners: list[tuple[int, dict[int, str]]] = []   # (seed, {match_num: winner})

    for s in seeds:
        result = simulate_bracket(matches, seed=s)
        champion_counts[result.match_winners[104]] += 1
        finalist_counts[result.match_winners[104]] += 1
        finalist_counts[result.match_losers[104]]  += 1
        for mn in (101, 102):
            semifinal_counts[result.match_winners[mn]] += 1
            semifinal_counts[result.match_losers[mn]]  += 1
        ko_winners: dict[int, str] = {}
        for m in result.matches:
            if m.stage != Stage.GROUP:
                mn = int(m.match_id[1:])
                match_winner_counts[mn][result.match_winners.get(mn, m.home)] += 1
                match_participant_counts[mn][m.home] += 1
                match_participant_counts[mn][m.away] += 1
                if mn in result.match_winners:
                    ko_winners[mn] = result.match_winners[mn]
        run_ko_winners.append((s, ko_winners))

    # Modal winner per KO match — the most frequent winner across all sims
    _mwc = {mn: dict(t) for mn, t in match_winner_counts.items()}
    modal: dict[int, str] = {
        mn: max(counts, key=counts.__getitem__)
        for mn, counts in _mwc.items()
    }

    # KO matches weighted by importance: later rounds count more
    _weights: dict[int, float] = {}
    for mn in range(73, 89):  _weights[mn] = 1.0   # R32
    for mn in range(89, 97):  _weights[mn] = 1.5   # R16
    for mn in range(97, 101): _weights[mn] = 2.0   # QF
    for mn in (101, 102):     _weights[mn] = 3.0   # SF
    _weights[103] = 1.5                             # 3rd place
    _weights[104] = 4.0                             # Final

    def _score(ko_winners: dict[int, str]) -> float:
        return sum(
            _weights.get(mn, 1.0)
            for mn, winner in ko_winners.items()
            if modal.get(mn) == winner
        )

    best_seed = max(run_ko_winners, key=lambda x: _score(x[1]))[0]
    representative = simulate_bracket(matches, seed=best_seed)

    return MonteCarloResult(
        n_sims                   = n,
        champion_counts          = dict(champion_counts),
        finalist_counts          = dict(finalist_counts),
        semifinal_counts         = dict(semifinal_counts),
        match_winner_counts      = _mwc,
        match_participant_counts = {mn: dict(t) for mn, t in match_participant_counts.items()},
        representative           = representative,
    )


# ── Simulation helpers ─────────────────────────────────────────────────────────

def _sim_ko(
    home: str,
    away: str,
    rng: random.Random,
) -> tuple[str, str, int, int]:
    """Simulate a knockout match → (winner, loser, home_goals, away_goals). No draws."""
    from classifier.elo import win_probability, current_elo
    p_home, _, p_away = win_probability(home, away, neutral=True)
    total = p_home + p_away
    p_hw = p_home / total if total > 0 else 0.5
    if rng.random() < p_hw:
        q_w = _elo_to_q(current_elo(home))
        q_l = _elo_to_q(current_elo(away))
        wg, lg = _sim_score(q_w, q_l, rng)
        return home, away, wg, lg
    else:
        q_w = _elo_to_q(current_elo(away))
        q_l = _elo_to_q(current_elo(home))
        wg, lg = _sim_score(q_w, q_l, rng)
        return away, home, lg, wg


def _poisson(lam: float, rng: random.Random) -> int:
    """Sample from Poisson(lam) via Knuth's algorithm. Suitable for lam < 30."""
    import math
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def _sim_score(q_winner: float, q_loser: float, rng: random.Random) -> tuple[int, int]:
    """
    Return (winner_goals, loser_goals) calibrated to WC historical distributions.

    Historical WC decisive matches:
      Winner goals: avg ~2.3 — 1(25%), 2(36%), 3(22%), 4(8%)
      Loser goals:  avg ~0.5 — 0(58%), 1(35%), 2(6%), 3(1%)
    Previous model (randint-based) produced avg 4.7 goals — far too high.

    Approach: sample loser goals and winning margin independently.
      l_goals ~ Poisson(lam_l)          — how well loser attacks
      margin  ~ Poisson(lam_m) + 1      — winning margin ≥ 1
      w_goals = l_goals + margin

    Parameters calibrated via grid search on WC 1930–2022 data:
      Quality scores range 0.06–0.86, mean ≈ 0.50.
    """
    gap   = q_winner - q_loser
    lam_l = 0.3 + q_loser * 0.8        # q=0.06→0.35  q=0.50→0.70  q=0.86→0.99
    lam_m = max(0.1, 0.5 + gap * 0.8)  # equal→0.5  big gap (0.8)→1.14

    l_goals = _poisson(lam_l, rng)
    margin  = 1 + _poisson(lam_m, rng)
    return l_goals + margin, l_goals


def _sim_draw_score(rng: random.Random) -> tuple[int, int]:
    """
    Return (goals, goals) for a draw, calibrated to WC data.
    Historical draw distribution: 0-0 (34%), 1-1 (39%), 2-2 (15%), 3-3 (3%).
    Poisson(0.9) fits well.
    """
    g = _poisson(0.9, rng)
    return g, g


def _simulate_groups(
    group_matches: list[Match],
    rng: random.Random,
) -> tuple[dict[str, list[dict]], dict[int, str], dict[int, tuple[int, int]]]:
    """
    Simulate all group stage matches using ELO-based probabilities.
    Returns ({group_letter: [{'team','pts','gd','gf'}, ...]}, {match_num: winner}, {match_num: (hg, ag)}).
    Standings sorted by pts → gd → gf (FIFA criteria 1-3 for best-third selection).
    """
    from classifier.elo import win_probability, current_elo

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

    match_winners: dict[int, str]              = {}
    match_scores:  dict[int, tuple[int, int]]  = {}

    for m in group_matches:
        if m.home == "TBD" or m.away == "TBD":
            continue
        p_home, p_draw, p_away = win_probability(m.home, m.away, neutral=True)
        r     = rng.random()
        hw    = p_home
        mn    = int(m.match_id[1:])
        if r < hw:
            q_h = _elo_to_q(current_elo(m.home))
            q_a = _elo_to_q(current_elo(m.away))
            hg, ag = _sim_score(q_h, q_a, rng)
            pts[m.home] += 3
            gf[m.home]  += hg;  gf[m.away]  += ag
            gd[m.home]  += hg - ag;  gd[m.away]  -= hg - ag
            match_winners[mn] = m.home
        elif r < hw + p_draw:
            hg, ag = _sim_draw_score(rng)
            pts[m.home] += 1;  pts[m.away] += 1
            gf[m.home]  += hg;  gf[m.away]  += ag
            match_winners[mn] = m.home if p_home >= p_away else m.away
        else:
            q_a = _elo_to_q(current_elo(m.away))
            q_h = _elo_to_q(current_elo(m.home))
            ag, hg = _sim_score(q_a, q_h, rng)
            pts[m.away] += 3
            gf[m.home]  += hg;  gf[m.away]  += ag
            gd[m.away]  += ag - hg;  gd[m.home]  -= ag - hg
            match_winners[mn] = m.away
        match_scores[mn] = (hg, ag)

    standings: dict[str, list[dict]] = {}
    for grp, teams in all_teams.items():
        table = sorted(
            teams,
            key=lambda t: (pts[t], gd[t], gf[t]),
            reverse=True,
        )
        standings[grp] = [{"team": t, "pts": pts[t], "gd": gd[t], "gf": gf[t]} for t in table]

    return standings, match_winners, match_scores


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
