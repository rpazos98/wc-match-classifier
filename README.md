# WC Match Classifier

A personalized recommendation engine for FIFA World Cup 2026 matches. Scores all 104 tournament matches on a 0–100 scale using 8 independent scorers, learns user preferences via Ridge regression on historical match ratings, and simulates the full tournament bracket with Monte Carlo methods (5,000 runs).

Built with FastAPI + React 18 / TypeScript. Spanish-language UI.

---

## How It Works

### Classification Tiers

Every match gets a composite score (0–100) and falls into one of three tiers:

| Tier | Score | Label |
|------|-------|-------|
| Imperdible | >= 60 | Must-watch |
| Vale la pena | >= 30 | Worth watching |
| Para ver el resumen | < 30 | Catch the highlights |

### The 8 Scorers

Each scorer produces a raw value (0.0–1.0), multiplied by its weight. All weights sum to 1.0.

| Scorer | Weight | What It Measures |
|--------|--------|-----------------|
| **Competitive Tension** | 0.21 | Shannon entropy of ELO win probabilities, scaled by prestige (avg ELO). Formula: `entropy^0.7 * (0.4 + 0.6 * prestige)` |
| **Favorite Team** | 0.19 | User affinity for teams in the match. Tiers: S=1.0, A=0.65, B=0.30. Secondary team adds up to 30% boost |
| **Match Stage** | 0.17 | Tournament importance. Group J1=0.20 up to Final=1.00. J3 matches get dynamic entropy boost |
| **Star Power** | 0.14 | Players rated 86+ OVR (EA FC26). Depth-weighted top-3 average per team. Dual-elite boost (1.4x) when both teams have 90+ stars |
| **Chaos Potential** | 0.12 | Expected goal volume from simulation. 4.5+ goals = "caótico", <2 = "cerrado". Without sim data: attack/fragility heuristic |
| **Form** | 0.08 | ELO momentum over last 8 matches, normalized to [0,1], weighted toward the hotter team |
| **Narrative** | 0.06 | Historical rivalry depth. 55% WC H2H rivalry + 30% drama (penalties, late goals, red cards) + 15% all-competition H2H |
| **Same Group** | 0.03 | Bonus for group-stage matches involving teams in the same group as user's favorites |

### Synergy Bonus: "Momento"

After all 8 scorers run, an additive bonus fires when a favorite team plays in a big stage:

```
if fav_raw > 0.3 AND stage_raw > 0.35:
    synergy = fav_raw * stage_raw * 8.0  (up to 8 pts added)
```

### Match Archetypes

Each match gets a character label derived from raw scorer values:

- **Decisive** — Stage >= 0.7
- **Chaos** — Chaos >= 0.6
- **Rivalry** — Narrative >= 0.4
- **Showcase** — Star Power >= 0.5
- **Tactical** — Tension >= 0.7 & Chaos < 0.55
- **Balanced** — Tension >= 0.6 (fallback)
- **Standard** — default (group match)

---

## ELO Rating System

Custom ELO implementation processing 49K+ international results (1872–2026).

- **Starting ELO:** 1500
- **Win probability:** `p_home = 1 / (1 + 10^((r_away - r_home) / 400))`
- **Home advantage:** +100 ELO (non-neutral venues)
- **K-factors by tournament:**
  - World Cup: 32
  - Continental championships: 28
  - WC qualification: 25
  - Friendlies: 10
- **Form delta:** ELO change over last 8 matches, normalized to [-1, 1]

---

## Monte Carlo Tournament Simulation

Runs the full 48-team bracket 5,000 times with stochastic outcomes.

### Two Engines

**Classic (default)**
- Composite ELO: `base_elo + quality_adj + form_adj + host_adj`
  - `quality_adj = (expected_from_quality - base) * 0.25`
  - `form_adj = form_delta * 50`
  - `host_adj = 60` for host nations (USA, CAN, MEX)
- Winner decided by ELO probability, goals from random distribution

**FTE538 (FiveThirtyEight-style)**
- Expected goals (xG) model with Poisson sampling:
  ```
  base = 1.25  (WC avg ~2.5 total)
  elo_adj = (r_home - r_away) / 650
  lambda = base + elo_adj + attack_bonus - defense_penalty
  ```
  Clamped to [0.2, 3.0] per team
- Confederation bonus: +20 ELO for CONCACAF teams at home
- Draw inflation: +9% on diagonal of score matrix

### Bracket Logic

- **Group stage:** Simulate all matches, compute standings
- **R32:** 16 matches pairing group winners, runners-up, and best 3rd-place teams
- **KO rounds:** R16 -> QF -> SF -> 3rd Place -> Final
- **Representative bracket:** Single most-aligned run (modal winner per KO match)
- **Aggregated outputs:** Champion probabilities, per-match winner frequencies, team paths through the bracket

---

## Preference Learning

Users rate historical World Cup matches (2018, 2022) on a 1–10 scale. The system learns personalized scorer weights.

### Feature Engineering

14-dimensional feature vector per match:
- 8 base features (raw scorer values)
- 6 interaction pairs (e.g., Favorite Team x Match Stage, Tension x Star Power)

### Model

- **< 5 ratings:** Pearson correlation as proxy
- **>= 5 ratings:** Ridge regression (alpha=1.0)
- **Confidence ramp:** Linear blend between default and learned weights
  ```
  alpha = min(1.0, n_ratings / 20)
  blended = (1 - alpha) * default_weights + alpha * learned_weights
  ```
  Full confidence at 20 ratings.

### Active Learning

Selects which historical matches to show next using uncertainty sampling:
- < 5 ratings: feature variance as proxy
- >= 5 ratings: bootstrap Ridge (50 resamples), pick matches with highest prediction std

---

## User Profile

```json
{
  "name": "string",
  "team_affinities": {"ARG": 1.0, "MEX": 0.65, "JPN": 0.30},
  "time_windows": [{"weekday": 6, "start_hour": 10, "end_hour": 22, "timezone": "America/Mexico_City"}],
  "language": "es",
  "region": "MX"
}
```

Team affinity tiers: **S** (1.0) = favorite, **A** (0.65) = like, **B** (0.30) = interesting.

All user state persists to `data/user_state.json`: profile, rated examples, learned weights, fit metadata.

---

## Database

SQLite (`data/wc2026.db`) with the following tables:

| Table | Purpose |
|-------|---------|
| `matches` | 104 WC 2026 matches (80 group + 24 KO) |
| `teams` | 48 qualified teams + group assignments |
| `team_metadata` | FIFA rank, confederation, WC titles/appearances, best finish |
| `players` | Full squad rosters with EA FC26 ratings (pace, shooting, passing, etc.) |
| `team_quality` | View: normalized avg top-11 overall rating per team |
| `wc_h2h` | World Cup head-to-head records between all team pairs |
| `all_h2h` | All-competition head-to-head records |
| `wc_drama` | Drama indicators: penalties, late goals, red cards, own goals per matchup |
| `host_cities` | 16 host venues across USA, Canada, Mexico |
| `tournament_stages` | Stage definitions (Group J1-J3, R32, R16, QF, SF, Final) |

### Data Sources

- **EA FC26** player ratings (`FC26_20250921.csv`)
- **International results** 1872–2026 (`intl_results/results.csv`) — used for ELO and H2H
- **World Cup match history** 1930–2022 (`wc_history/matches_1930_2022.csv`) — used for learning
- **Player profiles** from Transfermarkt (`player_profiles.csv`, `player_national_performances.csv`)

---

## API Endpoints

### Matches & Scoring
- `GET /api/matches` — All confirmed matches with scores, scorer breakdowns, and archetypes
- `GET /api/weights` — Scorer metadata (max points, labels, descriptions)

### Simulation
- `POST /api/simulate` — Run Monte Carlo (body: `{seed?, engine?: "classic"|"fte538"}`)
  - Returns: bracket rounds, group standings, champion odds, team paths

### Profile
- `GET /api/profile` — Current user profile
- `PUT /api/profile` — Update team affinities, time windows, name

### Learning
- `GET /api/learn/matches?n=15&years=2018,2022` — Historical matches for rating
- `POST /api/learn/fit-ratings` — Submit ratings, fit model, return new weights
- `DELETE /api/learn/ratings` — Reset all ratings to defaults
- `GET /api/learn/state` — Current learned weights, confidence, top features

### Teams
- `GET /api/teams` — All 48 WC 2026 teams with metadata

---

## Frontend

React 18 + TypeScript + Vite. Three main views:

### Matches Tab
- Sorted list of matches with score rings (0–100 visual gauge), tier labels, flags
- Filter by stage, sort by score/date
- Detail panel on selection: archetype, narrative, scorer contribution breakdown, win probabilities, H2H records, star players

### Bracket Tab
- Full tournament bracket visualization (R32 through Final)
- Predicted scores and win probabilities per match
- Group standings after simulation
- Champion odds (top 10 teams)
- Team path analysis (probability of reaching each round)

### Learn Tab
- Historical WC match cards (2018, 2022)
- 1–10 rating interface
- Post-fit summary: confidence level, top weighted features, method used

---

## Project Structure

```
wc-match-classifier/
├── web.py                      # FastAPI server, all API endpoints
├── main.py                     # Entry point
├── classifier/
│   ├── __init__.py             # classify_matches orchestrator
│   ├── classification.py       # Threshold-based tier assignment
│   ├── elo.py                  # ELO ratings, win probability, form delta
│   ├── historical.py           # Historical WC match loading for learning
│   ├── learning.py             # Ridge regression, active learning, feature engineering
│   ├── models.py               # UserProfile, TimeWindow, Match, Team dataclasses
│   ├── simulation.py           # Monte Carlo bracket simulation (Classic + FTE538)
│   └── scoring/
│       ├── __init__.py         # ScoringEngine, BaseScorer, MatchPrediction
│       ├── favorite_team.py    # Team affinity scorer
│       ├── competitive_tension.py  # Entropy + prestige scorer
│       ├── match_stage.py      # Tournament importance scorer
│       ├── star_power.py       # Elite player scorer
│       ├── chaos_potential.py  # Goal expectation scorer
│       ├── form.py             # ELO momentum scorer
│       ├── narrative.py        # Historical rivalry scorer
│       └── same_group.py       # Group-stage affinity scorer
├── db/
│   ├── build.py                # Database initialization and data ingestion
│   └── query.py                # SQL query helpers (H2H, rivalry, drama, stars)
├── data/
│   ├── wc2026.db               # SQLite database (built by db/build.py)
│   ├── user_state.json         # Persisted user profile + learned weights
│   ├── FC26_20250921.csv       # EA FC26 player ratings
│   ├── intl_results/           # International match results (1872–2026)
│   └── wc_history/             # Historical WC match data (1930–2022)
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main app shell
│   │   ├── state/AppContext.tsx # Global state management
│   │   ├── api/                # HTTP client + endpoint wrappers
│   │   ├── hooks/              # SWR data fetching hooks
│   │   ├── components/
│   │   │   ├── matches/        # MatchList, MatchCard, FilterBar
│   │   │   ├── detail/         # DetailPanel, ScoreRing, ContributionList
│   │   │   ├── bracket/        # BracketView, KOBracket, ChampionOdds
│   │   │   ├── learn/          # LearnModal, RatingButtons, LearnSummary
│   │   │   ├── profile/        # ProfileEditModal
│   │   │   └── layout/         # Header, Sidebar, TabBar
│   │   ├── types/index.ts      # TypeScript interfaces
│   │   └── utils/              # Formatting, flags, labels
│   └── vite.config.ts
├── static/                     # Compiled frontend assets
├── pyproject.toml              # Python dependencies
└── Makefile                    # Build/run commands
```

---

## Setup

```bash
# Backend
uv pip install -e .
python db/build.py          # Initialize database
python main.py              # Start FastAPI server

# Frontend
cd frontend
npm install
npm run dev                 # Dev server with HMR
npm run build               # Build to ../static/
```

---

## Tech Stack

- **Backend:** Python, FastAPI, NumPy, scikit-learn (Ridge regression)
- **Frontend:** React 18, TypeScript, Vite, SWR
- **Database:** SQLite
- **Simulation:** Custom Monte Carlo with ELO-based and xG-based engines
- **ML:** Ridge regression for preference learning, bootstrap uncertainty sampling for active learning
