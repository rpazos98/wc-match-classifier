"""
web.py — FastAPI web UI for Tu tiempo, tu Mundial 2026.

Stateless API — all user state (profile, learned weights) lives in the
browser's localStorage and is sent with each request.

Launch:
    uv run uvicorn web:app --reload
    uv run uvicorn web:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# CORS — allow GitHub Pages and local dev
`_CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,https://rpazos98.github.io",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Labels ────────────────────────────────────────────────────────────────────

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
    "Espectáculo":       "Espectáculo",
}

_SCORER_DESCS: dict[str, str] = {
    "Favorite Team":       "Qué tanto te importa este equipo",
    "Match Stage":         "Importancia de la ronda — los stakes son el predictor más robusto (Jennett 1984)",
    "Competitive Tension": "Paridad y prestigio — leve favorito > 50-50 puro (Vecer 2007)",
    "Chaos Potential":     "Goles esperados — más goles = más cambios de probabilidad (Vecer 2007)",
    "Narrative":           "Rivalidades históricas — efecto real pero inconsistente (Tyler 2024)",
    "Same Group":          "Partido entre equipos del mismo grupo",
    "Form":                "Momento actual de los equipos (racha reciente)",
    "Star Power":          "Calidad de figuras — el factor más fuerte según la evidencia (Cox 2023)",
    "Momento":             "Bonus por tu equipo en un partido de alta importancia",
    "Espectáculo":         "Parejo + goleador = emoción desproporcionada (Vecer 2007)",
}

_PERSONAL_SCORERS = {"Favorite Team", "Same Group", "Momento"}

_STAGE_NARRATIVE = {
    "group":       "fase de grupos",
    "r32":         "ronda de 32",
    "r16":         "octavos de final",
    "qf":          "cuartos de final",
    "sf":          "semifinal",
    "third_place": "tercer lugar",
    "final":       "la gran final",
}

# ── Helpers ────────────────────────────────────────────────────────────────────


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
    affinities = data.get("team_affinities", {})
    return UserProfile(
        name=data.get("name", "Fan"),
        team_affinities={t.upper(): float(v) for t, v in affinities.items()},
        time_windows=windows,
    )


_DEFAULT_PROFILE = _build_profile({"name": "Fan", "team_affinities": {}})


def _tz_from_profile(profile: UserProfile) -> ZoneInfo:
    return profile.time_windows[0].timezone if profile.time_windows else ZoneInfo("UTC")


def _active_engine(learned_weights: dict | None = None):
    engine = build_default_engine()
    if learned_weights:
        apply_learned_weights(engine, learned_weights)
    return engine


def _score_weights(learned_weights: dict | None = None) -> dict:
    engine = _active_engine(learned_weights)
    return {
        s.name: {
            "max_pts": round(s.weight * 100, 1),
            "label":   _SCORER_LABELS.get(s.name, s.name),
            "desc":    _SCORER_DESCS.get(s.name, ""),
        }
        for s in engine.scorers
    }


def _match_archetype(raw: dict[str, float], pred: dict | None, bd: dict[str, float]) -> dict:
    r_tension = raw.get("Competitive Tension", 0)
    r_chaos   = raw.get("Chaos Potential", 0)
    r_upset   = raw.get("Upset Potential", 0)
    r_stage   = raw.get("Match Stage", 0)
    r_narr    = raw.get("Narrative", 0)
    r_stars   = raw.get("Star Power", 0)

    entropy = pred.get("entropy", 0.5) if pred else 0.5

    archetypes = []

    if r_stage >= 0.7:
        archetypes.append(("decisive", "🔥", "Partido decisivo", r_stage))
    if r_tension >= 0.55 and r_chaos >= 0.55:
        score = (r_tension + r_chaos) / 2
        archetypes.append(("spectacle", "🎭", "Espectáculo asegurado", score))
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

    if r_tension >= 0.6:
        return {"key": "balanced", "icon": "⚖️", "label": "Partido equilibrado"}
    return {"key": "standard", "icon": "⚽", "label": "Partido de grupo"}


def _match_narrative(
    home: str, away: str, stage_val: str,
    raw: dict[str, float], pred: dict | None,
    archetype: dict,
) -> str:
    tension = raw.get("Competitive Tension", 0)
    chaos   = raw.get("Chaos Potential", 0)
    stage   = raw.get("Match Stage", 0)
    narr    = raw.get("Narrative", 0)
    entropy = pred.get("entropy", 0.5) if pred else 0.5

    parts = []
    stage_name = _STAGE_NARRATIVE.get(stage_val, "")
    if stage >= 0.75:
        parts.append(f"Partido de {stage_name} con todo en juego.")
    elif stage >= 0.35:
        parts.append(f"Encuentro de {stage_name} con implicaciones en la tabla.")
    else:
        parts.append(f"Duelo de {stage_name}.")

    if tension >= 0.55 and chaos >= 0.55:
        parts.append("Parejo y con goles esperados — la combinación que más emoción genera.")
    elif tension >= 0.7:
        parts.append("Equipos muy parejos — resultado completamente abierto.")
    elif chaos >= 0.6:
        parts.append("Partido abierto donde se esperan goles.")
    elif entropy < 0.6:
        parts.append("Un favorito claro, pero el fútbol siempre sorprende.")

    if narr >= 0.5:
        parts.append(f"Historia previa entre {home} y {away} añade tensión.")

    return " ".join(parts)


def _serialize_match(c, tz: ZoneInfo) -> dict:
    m     = c.result.match
    local = m.kickoff_utc.astimezone(tz)
    bd    = c.result.breakdown

    intrinsic = round(sum(v for k, v in bd.items() if k not in _PERSONAL_SCORERS), 1)
    personal  = round(sum(v for k, v in bd.items() if k in _PERSONAL_SCORERS), 1)

    raw = c.result.raw_by_scorer
    pred = c.result.prediction
    archetype = _match_archetype(raw, pred, bd)
    narrative = _match_narrative(m.home, m.away, m.stage.value, raw, pred, archetype)

    h2h = None
    h2h_all = None
    h2h_recent = None
    if m.home != "TBD" and m.away != "TBD":
        from db.query import wc_h2h_record, all_h2h_record, recent_h2h_matches
        h2h = wc_h2h_record(m.home, m.away)
        h2h_all = all_h2h_record(m.home, m.away)
        h2h_recent = recent_h2h_matches(m.home, m.away, n=5)

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


# ── Pydantic models ──────────────────────────────────────────────────────────

class _TimeWindowIn(BaseModel):
    weekday:    int | None = None
    start_hour: int
    end_hour:   int
    timezone:   str = "America/Mexico_City"


class _ProfileIn(BaseModel):
    name:             str = "Fan"
    team_affinities:  dict[str, float] = {}
    time_windows:     list[_TimeWindowIn] = []


class _MatchesIn(BaseModel):
    profile:          _ProfileIn = _ProfileIn()
    learned_weights:  dict[str, float] | None = None


class _SimIn(BaseModel):
    profile:          _ProfileIn = _ProfileIn()
    learned_weights:  dict[str, float] | None = None
    seed:             int | None = None
    engine:           str = "classic"


class _PreviewMatchIn(BaseModel):
    home:             str
    away:             str
    stage:            str
    profile:          _ProfileIn = _ProfileIn()
    learned_weights:  dict[str, float] | None = None


class _RatedMatch(BaseModel):
    raw:    dict[str, float]
    rating: int


class _FitRatingsIn(BaseModel):
    ratings: list[_RatedMatch]


# ── Routes ────────────────────────────────────────────────────────────────────

_REACT_DIST = Path(__file__).parent / "static" / "dist"
_VANILLA_HTML = Path(__file__).parent / "static" / "index.html"


@app.get("/")
def index():
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(react_index)
    return FileResponse(_VANILLA_HTML)


if _REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_REACT_DIST / "assets"), name="react-assets")


@app.post("/api/matches")
def get_matches(req: _MatchesIn = _MatchesIn()):
    profile = _build_profile(req.profile.model_dump())
    lw      = req.learned_weights
    tz      = _tz_from_profile(profile)

    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
    classed     = classify_matches(confirmed, profile, learned_weights=lw)
    return {
        "matches":         [_serialize_match(c, tz) for c in classed],
        "weights":         _score_weights(lw),
        "default_weights": {k: round(v, 4) for k, v in _DEFAULT_WEIGHTS.items()},
        "has_learned":     lw is not None,
    }


_MC_N_SIMS = 5000


@app.post("/api/simulate")
def simulate(req: _SimIn = _SimIn()):
    from classifier.simulation import run_monte_carlo, SimEngine
    from classifier.models import Stage

    profile = _build_profile(req.profile.model_dump())
    lw      = req.learned_weights
    tz      = _tz_from_profile(profile)

    engine_type = SimEngine.FTE538 if req.engine == "fte538" else SimEngine.CLASSIC
    seed        = req.seed if req.seed is not None else random.randint(0, 9999)
    all_matches = load_all_matches()
    confirmed   = {m for m in all_matches if m.home != "TBD" and m.away != "TBD"}

    mc  = run_monte_carlo(all_matches, n=_MC_N_SIMS, seed=seed, engine=engine_type)
    sim = mc.representative
    n   = mc.n_sims

    ko_by_num: dict[int, "Match"] = {
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
            loser  = sim.match_losers.get(mn, "?")
            score  = sim.match_scores.get(mn)
            win_prob = {
                t: round(c / n, 3)
                for t, c in mc.match_winner_counts.get(mn, {}).items()
            }
            ms.append({
                "match_num":   mn,
                "home":        m.home,
                "away":        m.away,
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

    matchup_rarity: dict[int, float] = {}
    for mn in range(73, 105):
        m_obj = ko_by_num.get(mn)
        if not m_obj:
            continue
        pc = mc.match_participant_counts.get(mn, {})
        h_pct = pc.get(m_obj.home, 0) / n
        a_pct = pc.get(m_obj.away, 0) / n
        matchup_rarity[mn] = round(min(h_pct, a_pct), 3)

    predicted_scores: dict[str, tuple[int, int]] = {
        f"M{mn:03d}": (hg, ag)
        for mn, (hg, ag) in sim.match_scores.items()
    }
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
    classed = classify_matches(all_sim_matches, profile,
                               avg_goals_for_scoring or predicted_scores,
                               learned_weights=lw)

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
        "weights":        _score_weights(lw),
    }


@app.get("/api/weights")
def get_weights():
    return _score_weights()


# ── Preference learning ──────────────────────────────────────────────────────

@app.get("/api/learn/matches")
def get_learn_matches(n: int = 15, seed: int | None = None, exclude: str = "", years: str = ""):
    from classifier.historical import sample_historical_matches
    exclude_ids = [x for x in exclude.split(",") if x]
    year_list = [int(y) for y in years.split(",") if y.strip().isdigit()] or None
    matches = sample_historical_matches(
        _DEFAULT_PROFILE, n=n, seed=seed, exclude_ids=exclude_ids, years=year_list,
    )
    return {"matches": matches, "total": len(matches)}


@app.post("/api/learn/fit-ratings")
def learn_fit_ratings(req: _FitRatingsIn):
    from classifier.learning import fit_from_ratings

    examples = [{"raw": rm.raw, "rating": rm.rating} for rm in req.ratings]
    result = fit_from_ratings(examples)

    scorer_labels = {s.name: _SCORER_LABELS.get(s.name, s.name)
                     for s in build_default_engine().scorers}
    result["scorer_labels"] = scorer_labels
    result["total_examples"] = len(examples)
    return result


@app.post("/api/matches/preview")
def preview_match(req: _PreviewMatchIn):
    from classifier.models import Match, Stage
    from db.query import load_squads

    profile = _build_profile(req.profile.model_dump())
    lw      = req.learned_weights

    home = req.home.upper()
    away = req.away.upper()

    try:
        stage = Stage(req.stage)
    except ValueError:
        return {"error": f"Invalid stage: {req.stage}"}

    if home == away:
        return {"error": "Home and away must be different teams"}

    squads = load_squads()
    m = Match(
        match_id=f"PREVIEW_{home}_{away}",
        home=home,
        away=away,
        kickoff_utc=datetime.now(timezone.utc),
        stage=stage,
        venue="Hipotético",
        home_squad=squads.get(home),
        away_squad=squads.get(away),
    )

    classed = classify_matches([m], profile, learned_weights=lw)
    if not classed:
        return {"error": "Could not classify match"}

    tz = _tz_from_profile(profile)
    return {
        "match":   _serialize_match(classed[0], tz),
        "weights": _score_weights(lw),
    }


@app.get("/api/teams")
def get_teams():
    from db.query import load_teams
    return load_teams()


# ── LLM integration ──────────────────────────────────────────────────────────

from classifier.llm import LMStudioClient as _LMStudioClient

_llm = _LMStudioClient()


@app.get("/api/llm/status")
def llm_status():
    return _llm.check_status()


class _LLMClassifyIn(BaseModel):
    match_ids: list[str] | None = None
    profile:   _ProfileIn = _ProfileIn()


@app.post("/api/llm/classify")
async def llm_classify(req: _LLMClassifyIn = _LLMClassifyIn()):
    profile     = _build_profile(req.profile.model_dump())
    tz          = _tz_from_profile(profile)
    all_matches = load_all_matches()
    confirmed   = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
    classed     = classify_matches(confirmed, profile)

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
        "name":             profile.name,
        "team_affinities":  profile.team_affinities,
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

    tz          = ZoneInfo("UTC")
    all_matches = load_all_matches()
    target      = next((m for m in all_matches if m.match_id == match_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Match not found")

    classed = classify_matches([target], _DEFAULT_PROFILE)
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
    profile_data = {"name": "Fan", "team_affinities": {}}

    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            explanation = await loop.run_in_executor(
                pool, _llm.explain_match, match_data, profile_data
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LM Studio error: {exc}")

    return {"match_id": match_id, "explanation": explanation}
