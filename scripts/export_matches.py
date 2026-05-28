"""
Pre-compute all match data and a representative simulation.

Outputs:
  frontend/public/data/matches.json    — 72 confirmed matches (instant load)
  frontend/public/data/simulation.json — full bracket from 5000 MC sims

Usage:
    uv run python scripts/export_matches.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from classifier import load_all_matches, classify_matches
from classifier.models import UserProfile, Stage
from classifier.simulation import run_monte_carlo, SimEngine
from classifier.learning import DEFAULT_WEIGHTS
from web import _serialize_match, _score_weights
from zoneinfo import ZoneInfo
from db.query import team_group_map


PROFILE = UserProfile(name="Neutral", team_affinities={}, time_windows=[])
TZ = ZoneInfo("UTC")
N_SIMS = 5000
OUT_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data"


def export_matches():
    all_matches = load_all_matches()
    confirmed = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
    classed = classify_matches(confirmed, PROFILE)

    matches = []
    for c in classed:
        d = _serialize_match(c, TZ)
        d["home_group"] = team_group_map().get(c.result.match.home)
        d["away_group"] = team_group_map().get(c.result.match.away)
        matches.append(d)

    output = {
        "matches": matches,
        "weights": _score_weights(),
        "default_weights": {k: round(v, 4) for k, v in DEFAULT_WEIGHTS.items()},
        "has_learned": False,
        "groups": team_group_map(),
    }

    path = OUT_DIR / "matches.json"
    path.write_text(json.dumps(output, ensure_ascii=False))
    print(f"  matches: {len(matches)} matches, {path.stat().st_size / 1024:.0f} KB")
    return all_matches, confirmed


def export_simulation(all_matches, confirmed):
    seed = 42
    mc = run_monte_carlo(all_matches, n=N_SIMS, seed=seed, engine=SimEngine.FTE538)
    sim = mc.representative
    n = mc.n_sims

    ko_by_num = {
        int(m.match_id[1:]): m
        for m in sim.matches
        if m.stage != Stage.GROUP
    }

    champion_odds = sorted(
        [{"team": t, "pct": round(c / n, 3)} for t, c in mc.champion_counts.items()],
        key=lambda x: x["pct"], reverse=True,
    )

    ko_stages = [
        ("RONDA DE 32",  list(range(73, 89))),
        ("16VOS",        list(range(89, 97))),
        ("CUARTOS",      list(range(97, 101))),
        ("SEMIFINALES",  list(range(101, 103))),
        ("TERCER LUGAR", [103]),
        ("GRAN FINAL",   [104]),
    ]
    rounds = []
    for label, nums in ko_stages:
        ms = []
        for mn in nums:
            m = ko_by_num.get(mn)
            if not m:
                continue
            winner = sim.match_winners.get(mn, "?")
            loser = sim.match_losers.get(mn, "?")
            score = sim.match_scores.get(mn)
            win_prob = {
                t: round(c / n, 3)
                for t, c in mc.match_winner_counts.get(mn, {}).items()
            }
            ms.append({
                "match_num": mn,
                "home": m.home,
                "away": m.away,
                "winner": winner,
                "loser": loser,
                "is_final": mn == 104,
                "is_third": mn == 103,
                "winner_prob": win_prob,
                "home_goals": score[0] if score else None,
                "away_goals": score[1] if score else None,
            })
        if ms:
            rounds.append({"label": label, "matches": ms})

    standings = [
        {
            "group": grp,
            "teams": [
                {**row, "qualified": i < 2, "third_place": i == 2}
                for i, row in enumerate(table)
            ],
        }
        for grp, table in sorted(sim.standings.items())
    ]

    _round_ranges = {
        "R32": range(73, 89), "R16": range(89, 97), "QF": range(97, 101),
        "SF": range(101, 103), "F": [104],
    }
    team_paths = {}
    all_teams_in_mc = set()
    for mn, tcounts in mc.match_participant_counts.items():
        all_teams_in_mc.update(tcounts.keys())
    for team in all_teams_in_mc:
        path = {}
        for rnd, mns in _round_ranges.items():
            appearances = sum(
                mc.match_participant_counts.get(mn, {}).get(team, 0) for mn in mns
            )
            path[rnd] = round(appearances / n, 3)
        path["Champ"] = round(mc.champion_counts.get(team, 0) / n, 3)
        team_paths[team] = path

    matchup_rarity = {}
    for mn in range(73, 105):
        m_obj = ko_by_num.get(mn)
        if not m_obj:
            continue
        pc = mc.match_participant_counts.get(mn, {})
        h_pct = pc.get(m_obj.home, 0) / n
        a_pct = pc.get(m_obj.away, 0) / n
        matchup_rarity[mn] = round(min(h_pct, a_pct), 3)

    predicted_scores = {
        f"M{mn:03d}": (hg, ag)
        for mn, (hg, ag) in sim.match_scores.items()
    }
    avg_goals = None
    if mc.match_avg_goals:
        avg_goals = {
            f"M{mn:03d}": (hg, ag)
            for mn, (hg, ag) in mc.match_avg_goals.items()
        }

    # Score all matches (group + KO) with simulation data
    all_sim_matches = sorted(
        list(confirmed) + list(ko_by_num.values()),
        key=lambda m: m.match_id,
    )
    classed = classify_matches(
        all_sim_matches, PROFILE,
        avg_goals or predicted_scores,
    )

    sim_matches = []
    for c in classed:
        mn = int(c.result.match.match_id[1:])
        d = _serialize_match(c, TZ)
        d["home_group"] = team_group_map().get(c.result.match.home)
        d["away_group"] = team_group_map().get(c.result.match.away)
        sc = predicted_scores.get(f"M{mn:03d}")
        if sc:
            d["home_goals"] = sc[0]
            d["away_goals"] = sc[1]
        if mn >= 73 and sc:
            hg, ag = sc
            if hg > ag:
                d["predicted_winner"] = c.result.match.home
            elif ag > hg:
                d["predicted_winner"] = c.result.match.away
        if mn >= 73:
            d["rarity"] = matchup_rarity.get(mn)
            d["home_path"] = team_paths.get(c.result.match.home)
            d["away_path"] = team_paths.get(c.result.match.away)
        sim_matches.append(d)

    output = {
        "seed": seed,
        "n_sims": n,
        "matches": sim_matches,
        "bracket_rounds": rounds,
        "standings": standings,
        "champion_odds": champion_odds,
        "team_paths": team_paths,
        "weights": _score_weights(),
    }

    path = OUT_DIR / "simulation.json"
    path.write_text(json.dumps(output, ensure_ascii=False))
    print(f"  simulation: {len(sim_matches)} matches, {path.stat().st_size / 1024:.0f} KB")


def export_teams():
    from db.query import load_teams
    teams = load_teams()
    path = OUT_DIR / "teams.json"
    path.write_text(json.dumps(teams, ensure_ascii=False))
    print(f"  teams: {len(teams)} teams, {path.stat().st_size / 1024:.0f} KB")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Exporting pre-computed data...")
    all_matches, confirmed = export_matches()
    export_simulation(all_matches, set(confirmed))
    export_teams()
    print("Done.")


if __name__ == "__main__":
    main()
