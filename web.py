"""
web.py — FastAPI web UI for Tu tiempo, tu Mundial 2026.

Launch:
    uv run uvicorn web:app --reload
    uv run uvicorn web:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import random
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from classifier.models import UserProfile, TimeWindow
from classifier import classify_matches, load_all_matches, build_default_engine


def _prewarm_embeddings() -> None:
    try:
        from classifier.embeddings import get_index
        get_index()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        await loop.run_in_executor(pool, _prewarm_embeddings)
    yield


app = FastAPI(title="WC 2026", lifespan=lifespan)

# ── Global state (single-user) ─────────────────────────────────────────────────

_profile = UserProfile(
    name="Fan Demo",
    favorite_teams=["ARG", "MEX"],
    favorite_players=["Messi", "Lozano", "De Paul"],
    time_windows=[
        TimeWindow(start_hour=14, end_hour=23, weekday=5,
                   timezone=ZoneInfo("America/Mexico_City")),
        TimeWindow(start_hour=11, end_hour=23, weekday=6,
                   timezone=ZoneInfo("America/Mexico_City")),
    ],
)

_STAGE_LABELS: dict[str, str] = {
    "group":       "Grupos",
    "r32":         "Ronda 32",
    "r16":         "16vos",
    "qf":          "Cuartos",
    "sf":          "Semifinal",
    "third_place": "3er Lugar",
    "final":       "FINAL",
}

_SCORER_LABELS: dict[str, str] = {
    "Favorite Team":     "Equipo fav.",
    "Time Availability": "Disponibil.",
    "Match Stage":       "Fase",
    "Form":              "Forma",
    "Favorite Player":   "Jugador fav.",
    "Match Drama":       "Drama",
    "Goal Fest":         "Goles",
    "Dark Horse":        "Sorpresa",
    "Upset Potential":   "David/Goliat",
    "Same Group":        "Mismo grupo",
    "Narrative Weight":  "Historia",
    "Team Strength":     "Calidad",
    "Rivalry":           "Rivalidad",
    "Confederation":     "Confederac.",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tz() -> ZoneInfo:
    return _profile.time_windows[0].timezone if _profile.time_windows else ZoneInfo("UTC")


def _serialize_match(c, tz: ZoneInfo) -> dict:
    m     = c.result.match
    local = m.kickoff_utc.astimezone(tz)
    return {
        "match_id":         m.match_id,
        "home":             m.home,
        "away":             m.away,
        "stage":            m.stage.value,
        "stage_label":      _STAGE_LABELS.get(m.stage.value, m.stage.value),
        "kickoff_utc":      m.kickoff_utc.isoformat(),
        "kickoff_local":    local.strftime("%d/%m %H:%M"),
        "venue":            m.venue,
        "score":            round(c.result.total_score, 1),
        "label":            c.label,
        "emoji":            c.emoji,
        "breakdown":        {k: round(v, 1) for k, v in c.result.breakdown.items()},
        "raw_by_scorer":    {k: round(v, 4) for k, v in c.result.raw_by_scorer.items()},
        "reason_by_scorer": c.result.reason_by_scorer,
        "reasons":          c.result.reasons,
    }


def _score_weights() -> dict:
    return {
        s.name: {
            "max_pts": round(s.weight * 100, 1),
            "label":   _SCORER_LABELS.get(s.name, s.name),
        }
        for s in build_default_engine().scorers
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/profile")
def get_profile():
    return {
        "name":             _profile.name,
        "favorite_teams":   _profile.favorite_teams,
        "favorite_players": _profile.favorite_players,
        "time_windows": [
            {"weekday": w.weekday, "start_hour": w.start_hour,
             "end_hour": w.end_hour, "timezone": str(w.timezone)}
            for w in _profile.time_windows
        ],
    }


@app.get("/api/matches")
def get_matches():
    tz          = _tz()
    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
    classed     = classify_matches(confirmed, _profile)
    return {"matches": [_serialize_match(c, tz) for c in classed], "weights": _score_weights()}


class _TimeWindowIn(BaseModel):
    weekday:    int | None = None
    start_hour: int
    end_hour:   int
    timezone:   str = "America/Mexico_City"


class _ProfileIn(BaseModel):
    name:             str
    favorite_teams:   list[str]
    favorite_players: list[str]
    time_windows:     list[_TimeWindowIn]


@app.put("/api/profile")
def update_profile(req: _ProfileIn):
    global _profile
    windows = []
    for w in req.time_windows:
        try:
            tz_obj = ZoneInfo(w.timezone)
        except Exception:
            tz_obj = ZoneInfo("America/Mexico_City")
        windows.append(TimeWindow(
            start_hour=w.start_hour, end_hour=w.end_hour,
            timezone=tz_obj, weekday=w.weekday,
        ))
    _profile = UserProfile(
        name=req.name,
        favorite_teams=[t.upper() for t in req.favorite_teams],
        favorite_players=req.favorite_players,
        time_windows=windows,
    )
    return get_matches()


class _SimIn(BaseModel):
    seed: int | None = None


_MC_N_SIMS = 500  # number of Monte Carlo iterations


@app.post("/api/simulate")
def simulate(req: _SimIn = _SimIn()):
    from classifier.simulation import run_monte_carlo
    from classifier.models import Stage

    seed        = req.seed if req.seed is not None else random.randint(0, 9999)
    tz          = _tz()
    all_matches = load_all_matches()
    confirmed   = {m for m in all_matches if m.home != "TBD" and m.away != "TBD"}

    mc          = run_monte_carlo(all_matches, n=_MC_N_SIMS, seed=seed)
    sim         = mc.consensus
    n           = mc.n_sims

    probable    = [m for m in sim.matches if m not in confirmed]
    classed     = classify_matches(probable, _profile)

    winners_by_mid = {f"M{mn:03d}": team for mn, team in sim.match_winners.items()}

    confirmed_winners = {
        m.match_id: winners_by_mid[m.match_id]
        for m in confirmed
        if m.match_id in winners_by_mid
    }

    # match_winner_prob: match_num → {team: probability 0–1}
    match_winner_prob: dict[str, dict[str, float]] = {}
    for mn, counts in mc.match_winner_counts.items():
        match_winner_prob[str(mn)] = {team: round(c / n, 3) for team, c in counts.items()}

    # champion_odds: [{team, pct}] sorted desc
    champion_odds = sorted(
        [{"team": t, "pct": round(c / n, 3)} for t, c in mc.champion_counts.items()],
        key=lambda x: x["pct"], reverse=True,
    )

    # Build path-consistent most-likely bracket.
    # Key rule: winner of each slot = whichever of the two path-consistent teams
    # won that slot more often across N sims.  Never use raw global max — that
    # can select a team not in the match (e.g. ENG winning the 3rd-place slot
    # when in this path ENG reached the final).
    _r16_feeds = {89:(74,77),90:(73,75),91:(76,78),92:(79,80),
                  93:(83,84),94:(81,82),95:(86,88),96:(85,87)}
    _qf_feeds  = {97:(89,90),98:(93,94),99:(91,92),100:(95,96)}
    _sf_feeds  = {101:(97,98),102:(99,100)}

    slot_home:   dict[int, str] = {}
    slot_away:   dict[int, str] = {}
    slot_winner: dict[int, str] = {}  # path-consistent winner

    def _pick_winner(mn: int, h: str, a: str) -> str:
        counts = mc.match_winner_counts.get(mn, {})
        return h if counts.get(h, 0) >= counts.get(a, 0) else a

    def _set_slot(mn: int, h: str, a: str) -> None:
        slot_home[mn]   = h
        slot_away[mn]   = a
        slot_winner[mn] = _pick_winner(mn, h, a)

    # R32: teams come from fixed group slots → use participant counts
    for mn in range(73, 89):
        parts = mc.match_participant_counts.get(mn, {})
        top2  = sorted(parts, key=parts.__getitem__, reverse=True)[:2]
        h = top2[0] if len(top2) > 0 else "TBD"
        a = top2[1] if len(top2) > 1 else "TBD"
        _set_slot(mn, h, a)

    # R16 → QF → SF: propagate slot_winner forward
    for mn, (fa, fb) in _r16_feeds.items():
        _set_slot(mn, slot_winner.get(fa, "TBD"), slot_winner.get(fb, "TBD"))

    for mn, (fa, fb) in _qf_feeds.items():
        _set_slot(mn, slot_winner.get(fa, "TBD"), slot_winner.get(fb, "TBD"))

    for mn, (fa, fb) in _sf_feeds.items():
        _set_slot(mn, slot_winner.get(fa, "TBD"), slot_winner.get(fb, "TBD"))

    # Final: SF winners
    _set_slot(104, slot_winner.get(101, "TBD"), slot_winner.get(102, "TBD"))

    # 3rd place: SF losers (= the team in the SF that is NOT the slot_winner)
    def _sf_loser(sf_mn: int) -> str:
        h, a = slot_home[sf_mn], slot_away[sf_mn]
        return a if slot_winner[sf_mn] == h else h

    _set_slot(103, _sf_loser(101), _sf_loser(102))

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
            home     = slot_home.get(mn, "TBD")
            away     = slot_away.get(mn, "TBD")
            winner   = slot_winner.get(mn, "?")
            loser    = away if winner == home else home
            win_prob = {t: round(c / n, 3) for t, c in mc.match_winner_counts.get(mn, {}).items()}
            ms.append({
                "match_num":   mn,
                "home":        home,
                "away":        away,
                "winner":      winner,
                "loser":       loser,
                "is_final":    mn == 104,
                "is_third":    mn == 103,
                "winner_prob": win_prob,
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

    return {
        "seed":              seed,
        "n_sims":            n,
        "confirmed_winners": confirmed_winners,
        "simulated": [
            {**_serialize_match(c, tz),
             "predicted_winner": winners_by_mid.get(c.result.match.match_id)}
            for c in classed
        ],
        "bracket_rounds":   rounds,
        "standings":        standings,
        "champion_odds":    champion_odds,
        "weights":          _score_weights(),
    }


class _DebugScoreIn(BaseModel):
    weights:              dict[str, float]
    threshold_imperdible: float = 60.0
    threshold_vale:       float = 30.0


@app.post("/api/debug-score")
def debug_score(req: _DebugScoreIn):
    from classifier.classification import (
        EMOJI, LABEL_IMPERDIBLE, LABEL_VALE, LABEL_RESUMEN, Classification,
    )

    tz          = _tz()
    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]

    engine  = build_default_engine()
    total_w = sum(req.weights.values())
    if total_w > 0:
        for scorer in engine.scorers:
            if scorer.name in req.weights:
                scorer.weight = req.weights[scorer.name] / total_w

    results = engine.evaluate_all(confirmed, _profile)

    def _classify(result):
        if result.total_score >= req.threshold_imperdible:
            label = LABEL_IMPERDIBLE
        elif result.total_score >= req.threshold_vale:
            label = LABEL_VALE
        else:
            label = LABEL_RESUMEN
        result.label = label
        return Classification(result=result, label=label, emoji=EMOJI[label])

    classed = [_classify(r) for r in results]

    custom_weights = {
        s.name: {"max_pts": round(s.weight * 100, 1), "label": _SCORER_LABELS.get(s.name, s.name)}
        for s in engine.scorers
    }

    return {
        "matches":    [_serialize_match(c, tz) for c in classed],
        "weights":    custom_weights,
        "thresholds": {"imperdible": req.threshold_imperdible, "vale": req.threshold_vale},
    }


@app.get("/api/weights")
def get_weights():
    return _score_weights()


# ── Preference learning ────────────────────────────────────────────────────────

@app.get("/api/learn/pairs")
def get_pairs(n: int = 12, seed: int | None = None, historical: bool = True):
    import random
    from classifier.learning import sample_pairs
    from classifier.historical import sample_historical_pairs

    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]

    if historical:
        # 50% current 2026 pairs, 50% historical — historical ones carry stronger signal
        # since the user actually experienced those matches
        n_hist    = n // 2
        n_current = n - n_hist
        hist_pairs    = sample_historical_pairs(_profile, n=n_hist, seed=seed)
        current_pairs = sample_pairs(confirmed, _profile, n=n_current, seed=seed)
        rng   = random.Random(seed)
        pairs = hist_pairs + current_pairs
        rng.shuffle(pairs)
    else:
        pairs = sample_pairs(confirmed, _profile, n=n, seed=seed)

    return {"pairs": pairs, "total": len(pairs)}


class _Preference(BaseModel):
    raw_a:     dict[str, float]
    raw_b:     dict[str, float]
    preferred: str   # "a" or "b"


class _FitIn(BaseModel):
    preferences: list[_Preference]


@app.post("/api/learn/fit")
def learn_fit(req: _FitIn):
    from classifier.learning import fit_weights
    prefs   = [{"raw_a": p.raw_a, "raw_b": p.raw_b, "preferred": p.preferred}
               for p in req.preferences]
    weights = fit_weights(prefs)
    # Also return label map so frontend can populate sliders
    labels  = {s.name: _SCORER_LABELS.get(s.name, s.name)
               for s in build_default_engine().scorers}
    return {"weights": weights, "labels": labels}


@app.get("/api/teams")
def get_teams():
    from db.query import load_teams
    return load_teams()


@app.get("/api/players/{team_code}")
def get_players(team_code: str):
    from db.query import players_by_team
    return players_by_team().get(team_code.upper(), [])


@app.get("/api/similar-players")
def get_similar_players():
    """
    For each fav player in the current profile, return WC-squad players
    with a similar style (by embedding cosine similarity).

    Response: { fav_player_name: [{name, sim, team}], ... }
    """
    try:
        from classifier.embeddings import get_index
        from db.query import _load_squads, _connect
    except Exception:
        return {}

    idx = get_index()
    con = _connect()
    squads = _load_squads(con)
    con.close()

    # Build: player_name → team_code
    player_to_team: dict[str, str] = {
        p: squad.team_code
        for squad in squads.values()
        for p in squad.players
    }
    all_wc_players = set(player_to_team)

    def _resolve(fav: str) -> str | None:
        """Resolve partial fav name (e.g. 'Messi') → index name (e.g. 'L. Messi')."""
        if fav in idx:
            return fav
        fav_lower = fav.lower()
        for name in idx._names:
            if fav_lower in name.lower():
                return name
        return None

    result: dict[str, list[dict]] = {}
    for fav in _profile.favorite_players:
        resolved = _resolve(fav)
        if not resolved:
            continue
        candidates = idx.similar_to(resolved, top_k=60, min_sim=0.88)
        in_wc = [
            {"name": name, "sim": round(sim, 3), "team": player_to_team[name]}
            for name, sim in candidates
            if name in all_wc_players
        ]
        if in_wc:
            result[fav] = in_wc[:6]

    return result
