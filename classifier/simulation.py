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


# ── Host nations (home advantage in WC 2026) ─────────────────────────────────
_HOST_CODES = frozenset({"USA", "CAN", "MEX"})
_HOST_ELO_BOOST = 60.0   # ~60 ELO ≈ home crowd boost (lower than full 100 since partial)


# ── Multi-factor team strength ────────────────────────────────────────────────

@dataclass
class _TeamProfile:
    elo: float
    quality: float     # 0-1 from FC26 squad ratings
    form: float        # -1 to 1 from ELO momentum
    attack: float      # 0-1 from top-11 shooting
    defense: float     # 0-1 from top-11 defending


_team_profiles_cache: dict[str, _TeamProfile] | None = None


def _load_team_profiles() -> dict[str, _TeamProfile]:
    global _team_profiles_cache
    if _team_profiles_cache is not None:
        return _team_profiles_cache

    from classifier.elo import current_elo, form_delta
    from db.query import (team_quality_scores, team_attack_scores,
                          team_defense_scores)

    quality = team_quality_scores()
    attack  = team_attack_scores()
    defense = team_defense_scores()

    profiles: dict[str, _TeamProfile] = {}
    all_codes = set(quality.keys()) | set(attack.keys()) | set(defense.keys())
    for code in all_codes:
        profiles[code] = _TeamProfile(
            elo     = current_elo(code),
            quality = quality.get(code, 0.4),
            form    = form_delta(code),
            attack  = attack.get(code, 0.5),
            defense = defense.get(code, 0.5),
        )

    _team_profiles_cache = profiles
    return profiles


def _composite_elo(code: str, is_home_host: bool = False) -> float:
    """
    Blend ELO with squad quality and form into a composite rating.

    Formula: base_elo + quality_adj + form_adj + host_adj
      - quality_adj: how much FC26 squad quality deviates from ELO expectation
      - form_adj: recent momentum (hot/cold streaks)
      - host_adj: home crowd boost for USA/CAN/MEX
    """
    profiles = _load_team_profiles()
    p = profiles.get(code)
    if not p:
        from classifier.elo import current_elo
        return current_elo(code) + (_HOST_ELO_BOOST if is_home_host else 0.0)

    # Base ELO
    base = p.elo

    # Quality adjustment: if squad is stronger/weaker than ELO suggests
    # Map quality (0-1) to expected ELO range (1300-2100), compare with actual
    expected_from_quality = 1300 + p.quality * 800
    quality_adj = (expected_from_quality - base) * 0.25  # 25% weight

    # Form adjustment: ±50 ELO for hot/cold streaks
    form_adj = p.form * 50.0

    # Host advantage
    host_adj = _HOST_ELO_BOOST if is_home_host else 0.0

    return base + quality_adj + form_adj + host_adj


def _composite_win_probability(
    home: str,
    away: str,
    home_venue: str = "",
) -> tuple[float, float, float]:
    """
    Multi-factor win probability using composite ELO.
    Returns (p_home, p_draw, p_away).
    """
    import math

    home_is_host = home in _HOST_CODES
    away_is_host = away in _HOST_CODES

    r_home = _composite_elo(home, is_home_host=home_is_host)
    r_away = _composite_elo(away, is_home_host=away_is_host)

    exp_home = 1.0 / (1.0 + 10.0 ** ((r_away - r_home) / 400.0))

    diff   = abs(r_home - r_away)
    p_draw = 0.28 * math.exp(-((diff / 200.0) ** 2))

    p_decisive = 1.0 - p_draw
    p_home     = exp_home * p_decisive
    p_away     = (1.0 - exp_home) * p_decisive

    return p_home, p_draw, p_away


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

    # Most likely champion
    modal_champion = max(champion_counts, key=champion_counts.__getitem__)

    # Step 1: filter runs where the modal champion wins
    champion_runs = [
        (s, kw) for s, kw in run_ko_winners
        if kw.get(104) == modal_champion
    ]
    if not champion_runs:
        champion_runs = run_ko_winners  # fallback

    # Step 2: compute modal winners WITHIN champion runs only
    # This ensures the representative path is coherent with the champion winning
    champ_modal: dict[int, str] = {}
    champ_match_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for _, kw in champion_runs:
        for mn, winner in kw.items():
            champ_match_counts[mn][winner] += 1
    for mn, counts in champ_match_counts.items():
        champ_modal[mn] = max(counts, key=counts.__getitem__)

    # KO matches weighted by importance: later rounds count more
    _weights: dict[int, float] = {}
    for mn in range(73, 89):  _weights[mn] = 1.0   # R32
    for mn in range(89, 97):  _weights[mn] = 1.5   # R16
    for mn in range(97, 101): _weights[mn] = 2.0   # QF
    for mn in (101, 102):     _weights[mn] = 3.0   # SF
    _weights[103] = 1.5                             # 3rd place
    _weights[104] = 5.0                             # Final

    def _score(ko_winners: dict[int, str]) -> float:
        return sum(
            _weights.get(mn, 1.0)
            for mn, winner in ko_winners.items()
            if champ_modal.get(mn) == winner
        )

    # Step 3: pick the champion run most aligned with champion-path modals
    best_seed = max(champion_runs, key=lambda x: _score(x[1]))[0]
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
    p_home, _, p_away = _composite_win_probability(home, away)
    total = p_home + p_away
    p_hw = p_home / total if total > 0 else 0.5
    profiles = _load_team_profiles()
    if rng.random() < p_hw:
        wg, lg = _sim_score_v2(profiles.get(home), profiles.get(away), rng)
        return home, away, wg, lg
    else:
        wg, lg = _sim_score_v2(profiles.get(away), profiles.get(home), rng)
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
    Legacy version using raw quality scores.
    """
    gap   = q_winner - q_loser
    lam_l = 0.3 + q_loser * 0.8
    lam_m = max(0.1, 0.5 + gap * 0.8)

    l_goals = _poisson(lam_l, rng)
    margin  = 1 + _poisson(lam_m, rng)
    return l_goals + margin, l_goals


def _sim_score_v2(
    winner: _TeamProfile | None,
    loser: _TeamProfile | None,
    rng: random.Random,
) -> tuple[int, int]:
    """
    Return (winner_goals, loser_goals) using team attack/defense profiles.

    Uses team-specific attack vs opponent defense rather than generic quality:
      - Loser goals driven by loser's attack vs winner's defense
      - Margin driven by ELO gap + winner's attack edge
    """
    if not winner or not loser:
        q_w = _elo_to_q(winner.elo if winner else 1500)
        q_l = _elo_to_q(loser.elo if loser else 1500)
        return _sim_score(q_w, q_l, rng)

    # Attack power: team's attack * (1 - opponent's defense dampening)
    w_power = winner.attack * (1.0 - loser.defense * 0.5)
    l_power = loser.attack * (1.0 - winner.defense * 0.5)

    # Loser goals: how much they can score despite losing
    lam_loser = 0.2 + l_power * 1.2

    # Winning margin: ELO gap + attack edge
    elo_gap = max(0.0, (winner.elo - loser.elo) / 800.0)
    attack_edge = max(0.0, w_power - l_power)
    lam_margin = max(0.1, 0.4 + elo_gap * 0.6 + attack_edge * 0.5)

    l_goals = _poisson(lam_loser, rng)
    margin  = 1 + _poisson(lam_margin, rng)
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
    team_group = _load_team_groups()
    profiles   = _load_team_profiles()

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
        p_home, p_draw, p_away = _composite_win_probability(m.home, m.away)
        r     = rng.random()
        hw    = p_home
        mn    = int(m.match_id[1:])
        if r < hw:
            hg, ag = _sim_score_v2(profiles.get(m.home), profiles.get(m.away), rng)
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
            ag, hg = _sim_score_v2(profiles.get(m.away), profiles.get(m.home), rng)
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
