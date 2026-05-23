"""
web.py — FastAPI web UI for Tu tiempo, tu Mundial 2026.

Launch:
    uv run uvicorn web:app --reload
    uv run uvicorn web:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from classifier.models import UserProfile, TimeWindow
from classifier import classify_matches, load_all_matches, build_default_engine, apply_learned_weights
from classifier.learning import DEFAULT_WEIGHTS as _DEFAULT_WEIGHTS


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

# ── Persistence ────────────────────────────────────────────────────────────────

_STATE_FILE = Path(__file__).parent / "data" / "user_state.json"

_DEFAULT_PROFILE_DATA = {
    "name":             "Fan Demo",
    "team_affinities":  {"ARG": 1.0, "MEX": 1.0},
    "time_windows": [],
}


def _build_profile(data: dict) -> UserProfile:
    windows = [
        TimeWindow(
            start_hour=w["start_hour"],
            end_hour=w["end_hour"],
            timezone=ZoneInfo(w.get("timezone", "America/Mexico_City")),
            weekday=w.get("weekday"),
        )
        for w in data.get("time_windows", [])
    ]
    # Backward compat: migrate old favorite_teams list
    affinities = data.get("team_affinities")
    if not affinities and data.get("favorite_teams"):
        affinities = {t.upper(): 1.0 for t in data["favorite_teams"]}
    return UserProfile(
        name=data.get("name", "Fan Demo"),
        team_affinities={t.upper(): float(v) for t, v in (affinities or {}).items()},
        time_windows=windows,
    )


def _load_state() -> tuple[UserProfile, list[dict], dict | None, dict | None]:
    """Load (profile, rated_examples, learned_weights, fit_meta) from disk."""
    if _STATE_FILE.exists():
        try:
            raw             = json.loads(_STATE_FILE.read_text())
            profile         = _build_profile(raw.get("profile", _DEFAULT_PROFILE_DATA))
            rated_examples  = raw.get("rated_examples", [])
            learned_weights = raw.get("learned_weights")
            fit_meta        = raw.get("fit_meta")
            return profile, rated_examples, learned_weights, fit_meta
        except Exception:
            pass
    return _build_profile(_DEFAULT_PROFILE_DATA), [], None, None


def _save_state() -> None:
    data = {
        "profile": {
            "name":             _profile.name,
            "team_affinities":  _profile.team_affinities,
            "time_windows": [
                {"weekday": w.weekday, "start_hour": w.start_hour,
                 "end_hour": w.end_hour, "timezone": str(w.timezone)}
                for w in _profile.time_windows
            ],
        },
        "rated_examples":  _rated_examples,
        "learned_weights": _learned_weights,
        "fit_meta":        _fit_meta,
    }
    _STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ── Global state (single-user) ─────────────────────────────────────────────────

_profile, _rated_examples, _learned_weights, _fit_meta = _load_state()

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
    "Favorite Team":       "Equipo fav.",
    "Match Stage":         "Fase",
    "Competitive Tension": "Tensión",
    "Chaos Potential":   "Caos",
    "Narrative":         "Historia",
    "Same Group":        "Mismo grupo",
    "Form":              "Forma",
    "Star Power":        "Estrellas",
    "Momento":           "Momento",
}

_SCORER_DESCS: dict[str, str] = {
    "Favorite Team":       "Qué tanto te importa este equipo",
    "Match Stage":         "Importancia de la ronda (grupo, octavos, final...)",
    "Competitive Tension": "Qué tan parejo es el partido según probabilidades",
    "Chaos Potential":     "Probabilidad de partido abierto y con muchos goles",
    "Narrative":           "Rivalidades históricas y contexto entre selecciones",
    "Same Group":          "Partido entre equipos del mismo grupo",
    "Form":                "Momento actual de los equipos (racha reciente)",
    "Star Power":          "Nivel de las figuras en cancha",
    "Momento":             "Bonus por tu equipo en un partido de alta importancia",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tz() -> ZoneInfo:
    return _profile.time_windows[0].timezone if _profile.time_windows else ZoneInfo("UTC")


_PERSONAL_SCORERS = {"Favorite Team", "Same Group", "Momento"}

# ── Match archetype + narrative ───────────────────────────────────────────────

_STAGE_NARRATIVE = {
    "group":       "fase de grupos",
    "r32":         "ronda de 32",
    "r16":         "octavos de final",
    "qf":          "cuartos de final",
    "sf":          "semifinal",
    "third_place": "tercer lugar",
    "final":       "la gran final",
}


def _match_archetype(raw: dict[str, float], pred: dict | None, bd: dict[str, float]) -> dict:
    """Derive emotional archetype from raw scorer profile."""
    r_tension = raw.get("Competitive Tension", 0)
    r_chaos   = raw.get("Chaos Potential", 0)
    r_upset   = raw.get("Upset Potential", 0)
    r_stage   = raw.get("Match Stage", 0)
    r_narr    = raw.get("Narrative", 0)
    r_stars   = raw.get("Star Power", 0)

    entropy = pred.get("entropy", 0.5) if pred else 0.5

    # Archetype is the dominant *character* of the match, based on raw values.
    # Each archetype requires a clear signal from its primary dimension.
    archetypes = []

    if r_stage >= 0.7:
        archetypes.append(("decisive", "🔥", "Partido decisivo", r_stage))
    if r_chaos >= 0.6:
        archetypes.append(("chaos", "⚡", "Partido abierto", r_chaos))
    if r_narr >= 0.4:
        archetypes.append(("rivalry", "⚔️", "Clásico con historia", r_narr))
    if r_stars >= 0.5:
        archetypes.append(("showcase", "👑", "Exhibición de estrellas", r_stars))
    if r_upset >= 0.8 and entropy < 0.80:
        archetypes.append(("upset", "💥", "Potencial de sorpresa", r_upset))
    if r_tension >= 0.7 and r_chaos < 0.55:
        archetypes.append(("tactical", "🧠", "Duelo táctico", r_tension))

    if archetypes:
        best = max(archetypes, key=lambda x: x[3])
        return {"key": best[0], "icon": best[1], "label": best[2]}

    # Fallback: describe by tension level
    if r_tension >= 0.6:
        return {"key": "balanced", "icon": "⚖️", "label": "Partido equilibrado"}
    return {"key": "standard", "icon": "⚽", "label": "Partido de grupo"}


def _match_narrative(
    home: str, away: str, stage_val: str,
    raw: dict[str, float], pred: dict | None,
    archetype: dict,
) -> str:
    """Generate a 1-2 sentence narrative from scorer data. No LLM needed."""
    tension = raw.get("Competitive Tension", 0)
    chaos   = raw.get("Chaos Potential", 0)
    stage   = raw.get("Match Stage", 0)
    narr    = raw.get("Narrative", 0)
    entropy = pred.get("entropy", 0.5) if pred else 0.5

    parts = []

    # Opening: what kind of match
    stage_name = _STAGE_NARRATIVE.get(stage_val, "")
    if stage >= 0.75:
        parts.append(f"Partido de {stage_name} con todo en juego.")
    elif stage >= 0.35:
        parts.append(f"Encuentro de {stage_name} con implicaciones en la tabla.")
    else:
        parts.append(f"Duelo de {stage_name}.")

    # Character: what to expect
    if tension >= 0.7 and chaos >= 0.6:
        parts.append("Se esperan emociones fuertes: equipos parejos y vocación ofensiva.")
    elif tension >= 0.7:
        parts.append("Equipos muy parejos — resultado completamente abierto.")
    elif chaos >= 0.6:
        parts.append("Partido abierto donde se esperan goles.")
    elif entropy < 0.6:
        parts.append("Un favorito claro, pero el fútbol siempre sorprende.")

    # Color: narrative or stars
    if narr >= 0.5:
        parts.append(f"Historia previa entre {home} y {away} añade tensión.")

    return " ".join(parts)


def _serialize_match(c, tz: ZoneInfo) -> dict:
    m     = c.result.match
    local = m.kickoff_utc.astimezone(tz)
    bd    = c.result.breakdown

    # Intrinsic score = sum of non-personal scorer contributions
    intrinsic = round(sum(v for k, v in bd.items() if k not in _PERSONAL_SCORERS), 1)
    personal  = round(sum(v for k, v in bd.items() if k in _PERSONAL_SCORERS), 1)

    raw = c.result.raw_by_scorer
    pred = c.result.prediction
    archetype = _match_archetype(raw, pred, bd)
    narrative = _match_narrative(m.home, m.away, m.stage.value, raw, pred, archetype)

    # H2H records
    h2h = None
    h2h_all = None
    h2h_recent = None
    if m.home != "TBD" and m.away != "TBD":
        from db.query import wc_h2h_record, all_h2h_record, recent_h2h_matches
        h2h = wc_h2h_record(m.home, m.away)
        h2h_all = all_h2h_record(m.home, m.away)
        h2h_recent = recent_h2h_matches(m.home, m.away, n=5)

    # Stars (players rated 86+)
    stars = []
    from db.query import player_overall_ratings
    ratings = player_overall_ratings()
    for squad in (m.home_squad, m.away_squad):
        if not squad:
            continue
        for p in squad.players:
            ovr = ratings.get(p)
            if ovr and ovr >= 86:
                stars.append({"name": p, "team": squad.team_code, "overall": ovr})
    stars.sort(key=lambda s: s["overall"], reverse=True)

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
        "archetype":        archetype,
        "narrative":        narrative,
        "breakdown":        {k: round(v, 1) for k, v in bd.items()},
        "raw_by_scorer":    {k: round(v, 4) for k, v in raw.items()},
        "weight_by_scorer": {k: round(v, 4) for k, v in c.result.weight_by_scorer.items()},
        "reason_by_scorer": c.result.reason_by_scorer,
        "detail_by_scorer": c.result.detail_by_scorer or {},
        "reasons":          c.result.reasons,
        "prediction":       pred,
        "intrinsic_score":  intrinsic,
        "personal_score":   personal,
        "h2h":              h2h,
        "h2h_all":          h2h_all,
        "h2h_recent":       h2h_recent if h2h_recent else None,
        "stars":            stars if stars else None,
        "base_score":       round(
            sum(v * _DEFAULT_WEIGHTS.get(k, 0) * 100 for k, v in raw.items()),
            1,
        ),
    }


def _active_engine():
    """Return engine with learned weights applied, if any."""
    engine = build_default_engine()
    if _learned_weights:
        apply_learned_weights(engine, _learned_weights)
    return engine


def _score_weights() -> dict:
    engine = _active_engine()
    return {
        s.name: {
            "max_pts": round(s.weight * 100, 1),
            "label":   _SCORER_LABELS.get(s.name, s.name),
            "desc":    _SCORER_DESCS.get(s.name, ""),
        }
        for s in engine.scorers
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

_REACT_DIST = Path(__file__).parent / "static" / "dist"
_VANILLA_HTML = Path(__file__).parent / "static" / "index.html"


@app.get("/")
def index():
    # Serve React build if available, otherwise fallback to vanilla
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(react_index)
    return FileResponse(_VANILLA_HTML)


# Serve React static assets (JS, CSS) from /assets/*
if _REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_REACT_DIST / "assets"), name="react-assets")


@app.get("/api/profile")
def get_profile():
    return {
        "name":             _profile.name,
        "team_affinities":  _profile.team_affinities,
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
    classed     = classify_matches(confirmed, _profile, learned_weights=_learned_weights)
    return {
        "matches":         [_serialize_match(c, tz) for c in classed],
        "weights":         _score_weights(),
        "default_weights": {k: round(v, 4) for k, v in _DEFAULT_WEIGHTS.items()},
        "has_learned":     _learned_weights is not None,
    }


class _TimeWindowIn(BaseModel):
    weekday:    int | None = None
    start_hour: int
    end_hour:   int
    timezone:   str = "America/Mexico_City"


class _ProfileIn(BaseModel):
    name:             str
    team_affinities:  dict[str, float] = {}
    favorite_teams:   list[str] = []    # legacy field — migrated on read
    time_windows:     list[_TimeWindowIn] = []


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
    affinities = req.team_affinities or {t.upper(): 1.0 for t in req.favorite_teams}
    _profile = UserProfile(
        name=req.name,
        team_affinities={t.upper(): float(v) for t, v in affinities.items()},
        time_windows=windows,
    )
    _save_state()
    return get_matches()


class _SimIn(BaseModel):
    seed: int | None = None


_MC_N_SIMS = 5000  # number of Monte Carlo iterations


@app.post("/api/simulate")
def simulate(req: _SimIn = _SimIn()):
    from classifier.simulation import run_monte_carlo
    from classifier.models import Stage

    seed        = req.seed if req.seed is not None else random.randint(0, 9999)
    tz          = _tz()
    all_matches = load_all_matches()
    confirmed   = {m for m in all_matches if m.home != "TBD" and m.away != "TBD"}

    mc  = run_monte_carlo(all_matches, n=_MC_N_SIMS, seed=seed)
    sim = mc.representative  # most MC-aligned run — source of truth for all displayed results
    n   = mc.n_sims

    # ── Single-run lookup tables ───────────────────────────────────────────────
    ko_by_num: dict[int, "Match"] = {
        int(m.match_id[1:]): m
        for m in sim.matches
        if m.stage != Stage.GROUP
    }

    # ── MC overlays (probabilities only — not used to select displayed teams) ──
    champion_odds = sorted(
        [{"team": t, "pct": round(c / n, 3)} for t, c in mc.champion_counts.items()],
        key=lambda x: x["pct"], reverse=True,
    )

    # ── Bracket: built entirely from the single simulation run ─────────────────
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
            home   = m.home
            away   = m.away
            winner = sim.match_winners.get(mn, "?")
            loser  = sim.match_losers.get(mn, "?")
            score  = sim.match_scores.get(mn)
            win_prob = {
                t: round(c / n, 3)
                for t, c in mc.match_winner_counts.get(mn, {}).items()
            }
            ms.append({
                "match_num":   mn,
                "home":        home,
                "away":        away,
                "winner":      winner,
                "loser":       loser,
                "is_final":    mn == 104,
                "is_third":    mn == 103,
                "winner_prob": win_prob,
                "home_goals":  score[0] if score else None,
                "away_goals":  score[1] if score else None,
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

    # ── Team tournament paths ─────────────────────────────────────────────────
    # For each team, compute probability of reaching each KO round
    _round_ranges = {
        "R32": range(73, 89), "R16": range(89, 97), "QF": range(97, 101),
        "SF": range(101, 103), "F": [104],
    }
    team_paths: dict[str, dict[str, float]] = {}
    all_teams_in_mc = set()
    for mn, tcounts in mc.match_participant_counts.items():
        all_teams_in_mc.update(tcounts.keys())

    for team in all_teams_in_mc:
        path: dict[str, float] = {}
        for rnd, mns in _round_ranges.items():
            appearances = sum(
                mc.match_participant_counts.get(mn, {}).get(team, 0) for mn in mns
            )
            path[rnd] = round(appearances / n, 3)
        path["Champ"] = round(mc.champion_counts.get(team, 0) / n, 3)
        team_paths[team] = path

    # ── Match rarity (for KO matches) ────────────────────────────────────────
    # How often does this specific home-away pairing occur across simulations?
    matchup_rarity: dict[int, float] = {}
    for mn in range(73, 105):
        m_obj = ko_by_num.get(mn)
        if not m_obj:
            continue
        pc = mc.match_participant_counts.get(mn, {})
        # Both teams need to appear in this slot — joint probability
        h_pct = pc.get(m_obj.home, 0) / n
        a_pct = pc.get(m_obj.away, 0) / n
        matchup_rarity[mn] = round(min(h_pct, a_pct), 3)

    # ── Unified match list ─────────────────────────────────────────────────────
    # Representative scores for display
    predicted_scores: dict[str, tuple[int, int]] = {
        f"M{mn:03d}": (hg, ag)
        for mn, (hg, ag) in sim.match_scores.items()
    }
    # Average goals across all sims for scoring (smoother than single-run noise)
    avg_goals_for_scoring: dict[str, tuple[float, float]] | None = None
    if mc.match_avg_goals:
        avg_goals_for_scoring = {
            f"M{mn:03d}": (hg, ag)
            for mn, (hg, ag) in mc.match_avg_goals.items()
        }

    all_sim_matches = sorted(
        list(confirmed) + list(ko_by_num.values()),
        key=lambda m: m.match_id,
    )
    classed = classify_matches(all_sim_matches, _profile,
                               avg_goals_for_scoring or predicted_scores,
                               learned_weights=_learned_weights)

    def _sim_entry(c) -> dict:
        mn = int(c.result.match.match_id[1:])
        d  = _serialize_match(c, tz)
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
        # KO match extras
        if mn >= 73:
            d["rarity"] = matchup_rarity.get(mn)
            d["home_path"] = team_paths.get(c.result.match.home)
            d["away_path"] = team_paths.get(c.result.match.away)
        return d

    return {
        "seed":           seed,
        "n_sims":         n,
        "matches":        [_sim_entry(c) for c in classed],
        "bracket_rounds": rounds,
        "standings":      standings,
        "champion_odds":  champion_odds,
        "team_paths":     team_paths,
        "weights":        _score_weights(),
    }



@app.get("/api/weights")
def get_weights():
    return _score_weights()


# ── Preference learning ────────────────────────────────────────────────────────

@app.get("/api/learn/matches")
def get_learn_matches(n: int = 15, seed: int | None = None, exclude: str = "", years: str = ""):
    from classifier.historical import sample_historical_matches
    exclude_ids = [x for x in exclude.split(",") if x]
    year_list = [int(y) for y in years.split(",") if y.strip().isdigit()] or None
    matches = sample_historical_matches(_profile, n=n, seed=seed, exclude_ids=exclude_ids, years=year_list)
    return {"matches": matches, "total": len(matches)}


class _RatedMatch(BaseModel):
    raw:    dict[str, float]
    rating: int   # 1–10


class _FitRatingsIn(BaseModel):
    ratings: list[_RatedMatch]


@app.post("/api/learn/fit-ratings")
def learn_fit_ratings(req: _FitRatingsIn):
    global _rated_examples, _learned_weights, _fit_meta
    from classifier.learning import fit_from_ratings

    new_examples = [{"raw": rm.raw, "rating": rm.rating} for rm in req.ratings]

    # Deduplicate by (raw vector hash) before accumulating
    existing_keys = {
        tuple(sorted(e["raw"].items())) for e in _rated_examples
    }
    for ex in new_examples:
        key = tuple(sorted(ex["raw"].items()))
        if key not in existing_keys:
            _rated_examples.append(ex)
            existing_keys.add(key)

    result = fit_from_ratings(_rated_examples)

    _learned_weights = result["weights"]
    _fit_meta = {
        "n":               result["rating_stats"].get("n", 0),
        "mean_rating":     result["rating_stats"].get("mean"),
        "confidence":      result.get("confidence", 0.0),
        "top_features":    [f["scorer"] for f in result.get("top_features", [])[:3]],
        "last_fit":        datetime.now(timezone.utc).isoformat(),
    }
    _save_state()

    scorer_labels = {s.name: _SCORER_LABELS.get(s.name, s.name)
                     for s in build_default_engine().scorers}
    result["scorer_labels"] = scorer_labels
    result["total_examples"] = len(_rated_examples)
    return result


@app.delete("/api/learn/ratings")
def reset_ratings():
    """Clear all accumulated ratings and revert to default weights."""
    global _rated_examples, _learned_weights, _fit_meta
    _rated_examples  = []
    _learned_weights = None
    _fit_meta        = None
    _save_state()
    return {"status": "reset", "message": "Ratings borrados. Pesos vueltos a default."}


@app.get("/api/learn/state")
def get_learn_state():
    """Return current learning state: n_examples, learned_weights, fit_meta."""
    from classifier.learning import DEFAULT_WEIGHTS
    return {
        "n_examples":       len(_rated_examples),
        "has_learned":      _learned_weights is not None,
        "learned_weights":  _learned_weights,
        "default_weights":  DEFAULT_WEIGHTS,
        "fit_meta":         _fit_meta,
        "weight_delta":     {
            k: round(_learned_weights[k] - DEFAULT_WEIGHTS.get(k, 0.0), 4)
            for k in (_learned_weights or {})
        } if _learned_weights else {},
    }


@app.get("/api/teams")
def get_teams():
    from db.query import load_teams
    return load_teams()


# ── LLM integration ───────────────────────────────────────────────────────────

from classifier.llm import LMStudioClient as _LMStudioClient

_llm = _LMStudioClient()


@app.get("/api/llm/status")
def llm_status():
    return _llm.check_status()


class _LLMClassifyIn(BaseModel):
    match_ids: list[str] | None = None   # None = all confirmed matches


@app.post("/api/llm/classify")
async def llm_classify(req: _LLMClassifyIn = _LLMClassifyIn()):
    tz          = _tz()
    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
    classed     = classify_matches(confirmed, _profile)

    match_data: list[dict] = []
    for c in classed:
        m = c.result.match
        if req.match_ids and m.match_id not in req.match_ids:
            continue
        local = m.kickoff_utc.astimezone(tz)
        match_data.append({
            "match_id":      m.match_id,
            "home":          m.home,
            "away":          m.away,
            "stage_label":   _STAGE_LABELS.get(m.stage.value, m.stage.value),
            "kickoff_local": local.strftime("%d/%m %H:%M"),
            "label":         c.label,
            "score":         round(c.result.total_score, 1),
            "raw_by_scorer": {k: round(v, 3) for k, v in c.result.raw_by_scorer.items()},
        })

    profile_data = {
        "name":             _profile.name,
        "team_affinities":  _profile.team_affinities,
    }

    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            llm_results = await loop.run_in_executor(
                pool, _llm.classify_matches, match_data, profile_data
            )
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"LM Studio error: {exc}")

    # Normalize match_ids from LLM (models sometimes prepend ": " or add spaces)
    import re as _re
    def _norm_mid(s: str) -> str:
        m = _re.search(r'M\d+', str(s).upper())
        return m.group(0) if m else s.strip()

    llm_by_id  = {_norm_mid(r["match_id"]): r for r in llm_results if r.get("match_id")}
    comparison = [
        {
            **m,
            "llm_label":     llm_by_id.get(m["match_id"], {}).get("label"),
            "llm_score":     llm_by_id.get(m["match_id"], {}).get("score"),
            "llm_reasoning": llm_by_id.get(m["match_id"], {}).get("reasoning"),
        }
        for m in match_data
    ]
    return {"results": comparison}


@app.get("/api/llm/explain/{match_id}")
async def llm_explain(match_id: str):
    from fastapi import HTTPException

    tz          = _tz()
    all_matches = load_all_matches()
    target      = next((m for m in all_matches if m.match_id == match_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Match not found")

    classed = classify_matches([target], _profile)
    if not classed:
        raise HTTPException(status_code=404, detail="Could not classify match")

    c     = classed[0]
    m     = c.result.match
    local = m.kickoff_utc.astimezone(tz)

    match_data = {
        "match_id":      m.match_id,
        "home":          m.home,
        "away":          m.away,
        "stage_label":   _STAGE_LABELS.get(m.stage.value, m.stage.value),
        "kickoff_local": local.strftime("%d/%m %H:%M"),
        "venue":         m.venue,
        "label":         c.label,
        "score":         round(c.result.total_score, 1),
        "raw_by_scorer": {k: round(v, 3) for k, v in c.result.raw_by_scorer.items()},
    }
    profile_data = {
        "name":             _profile.name,
        "team_affinities":  _profile.team_affinities,
    }

    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            explanation = await loop.run_in_executor(
                pool, _llm.explain_match, match_data, profile_data
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LM Studio error: {exc}")

    return {"match_id": match_id, "explanation": explanation}


