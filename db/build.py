"""
Extend wc2026.db with:
  - team_metadata  : FIFA rank, confederation, WC history
  - players        : FC26 national team players (WC-qualified teams only)
  - team_quality   : computed aggregate ratings per team (VIEW)
  - wc_h2h         : head-to-head WC records between teams

Usage:
    python -m db.build
"""
import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH      = Path(__file__).parent.parent / "data" / "wc2026.db"
CSV_PATH     = Path(__file__).parent.parent / "data" / "FC26_20250921.csv"
INTL_RESULTS  = Path(__file__).parent.parent / "data" / "intl_results" / "results.csv"
INTL_SCORERS  = Path(__file__).parent.parent / "data" / "intl_results" / "goalscorers.csv"

# ── FC26 nationality name → FIFA code mapping ─────────────────────────────────
# Covers all WC 2026 teams that have players in the FC26 CSV by nationality.
# Teams with nation_team_id set use official squad data (source='fc26_squad').
# Teams without use top-26 by overall rating as proxy (source='fc26_nationality').
FC26_NAME_TO_CODE: dict[str, str] = {
    # Nations with official FC26 national team squads (nation_team_id set)
    "Argentina":          "ARG",
    "Croatia":            "CRO",
    "England":            "ENG",
    "France":             "FRA",
    "Germany":            "GER",
    "Ghana":              "GHA",
    "Mexico":             "MEX",
    "Morocco":            "MAR",
    "Netherlands":        "NED",
    "Norway":             "NOR",
    "Portugal":           "POR",
    "Qatar":              "QAT",
    "Scotland":           "SCO",
    "Spain":              "ESP",
    "United States":      "USA",
    # Nations without FC26 squad tag — use nationality-based top-26 proxy
    "Bosnia and Herzegovina": "BIH",
    "Sweden":             "SWE",
    "Türkiye":            "TUR",   # FC26 uses Turkish spelling
    "Czechia":            "CZE",   # FC26 uses Czechia not Czech Republic
    "Congo DR":           "COD",   # DR Congo
    "Iraq":               "IRQ",
    "Algeria":            "ALG",
    "Austria":            "AUT",
    "Cabo Verde":         "CPV",
    "Curacao":            "CUR",   # FC26 drops the accent
    "Haiti":              "HAI",
    "Jordan":             "JOR",
    "New Zealand":        "NZL",
    "Paraguay":           "PAR",
    "Tunisia":            "TUN",
    "Uzbekistan":         "UZB",
    "Australia":          "AUS",
    "Belgium":            "BEL",
    "Brazil":             "BRA",
    "Canada":             "CAN",
    "Colombia":           "COL",
    "Côte d'Ivoire":      "CIV",
    "Ecuador":            "ECU",
    "Egypt":              "EGY",
    "Iran":               "IRN",
    "Japan":              "JPN",
    "Korea Republic":     "KOR",
    "Nigeria":            "NGA",
    "Panama":             "PAN",
    "Saudi Arabia":       "KSA",
    "Senegal":            "SEN",
    "South Africa":       "RSA",
    "Switzerland":        "SUI",
    "Uruguay":            "URU",
}

# ── Team metadata ──────────────────────────────────────────────────────────────
# (fifa_code, confederation, fifa_rank, wc_titles, wc_appearances, best_finish)
TEAM_METADATA = [
    ("ARG", "CONMEBOL",  1, 3, 18, "Winner"),
    ("FRA", "UEFA",      2, 2, 16, "Winner"),
    ("ENG", "UEFA",      3, 1, 16, "Winner"),
    ("ESP", "UEFA",      4, 1, 16, "Winner"),
    ("BRA", "CONMEBOL",  5, 5, 22, "Winner"),
    ("POR", "UEFA",      6, 0, 8,  "3rd Place"),
    ("BEL", "UEFA",      7, 0, 14, "3rd Place"),
    ("NED", "UEFA",      8, 0, 11, "Runner-up"),
    ("GER", "UEFA",      9, 4, 20, "Winner"),
    ("URU", "CONMEBOL", 10, 2, 14, "Winner"),
    ("COL", "CONMEBOL", 11, 0, 6,  "Quarterfinals"),
    ("MAR", "CAF",      12, 0, 7,  "4th Place"),
    ("USA", "CONCACAF", 13, 0, 11, "3rd Place"),
    ("MEX", "CONCACAF", 14, 0, 17, "Quarterfinals"),
    ("CRO", "UEFA",     15, 0, 6,  "Runner-up"),
    ("ITA", "UEFA",     16, 4, 18, "Winner"),   # not qualified
    ("DEN", "UEFA",     17, 0, 5,  "Quarterfinals"),
    ("SUI", "UEFA",     18, 0, 12, "Quarterfinals"),
    ("ECU", "CONMEBOL", 19, 0, 4,  "Round of 16"),
    ("SEN", "CAF",      20, 0, 3,  "4th Place"),
    ("JPN", "AFC",      21, 0, 7,  "Quarterfinals"),
    ("AUS", "AFC",      22, 0, 6,  "4th Place"),
    ("POL", "UEFA",     23, 0, 8,  "3rd Place"),
    ("KOR", "AFC",      24, 0, 11, "4th Place"),
    ("NOR", "UEFA",     25, 0, 3,  "Quarterfinals"),
    ("GHA", "CAF",      26, 0, 4,  "Quarterfinals"),
    ("CAN", "CONCACAF", 27, 0, 2,  "Group Stage"),
    ("CMR", "CAF",      28, 0, 8,  "Quarterfinals"),
    ("SRB", "UEFA",     29, 0, 1,  "Group Stage"),
    ("TUN", "CAF",      30, 0, 6,  "Group Stage"),
    ("NGA", "CAF",      31, 0, 7,  "Quarterfinals"),
    ("PAR", "CONMEBOL", 32, 0, 8,  "Runner-up"),
    ("IRN", "AFC",      33, 0, 6,  "Group Stage"),
    ("EGY", "CAF",      34, 0, 3,  "Round of 32"),
    ("KSA", "AFC",      35, 0, 6,  "Round of 16"),
    ("QAT", "AFC",      36, 0, 2,  "Group Stage"),
    ("SCO", "UEFA",     37, 0, 3,  "Group Stage"),
    ("AUT", "UEFA",     38, 0, 7,  "3rd Place"),
    ("ALG", "CAF",      39, 0, 4,  "Round of 16"),
    ("RSA", "CAF",      40, 0, 3,  "Group Stage"),
    ("CIV", "CAF",      41, 0, 3,  "Round of 16"),
    ("PAN", "CONCACAF", 42, 0, 2,  "Group Stage"),
    ("CUR", "CONCACAF", 43, 0, 0,  "Debut"),
    ("CPV", "CAF",      44, 0, 0,  "Debut"),
    ("HAI", "CONCACAF", 45, 0, 1,  "Group Stage"),
    ("JOR", "AFC",      46, 0, 0,  "Debut"),
    ("UZB", "AFC",      47, 0, 0,  "Debut"),
    ("NZL", "OFC",      48, 0, 2,  "Group Stage"),
]


def build(db_path: Path = DB_PATH, csv_path: Path = CSV_PATH) -> None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    _create_team_metadata(con)
    _create_players_table(con)
    _ingest_fc26_players(con, csv_path)
    _create_team_quality_table(con)

    if INTL_RESULTS.exists():
        _ingest_intl_results(con, INTL_RESULTS, INTL_SCORERS)
    else:
        print("  intl_results CSVs not found — skipping")

    _resolve_placeholders(con)

    con.commit()
    con.close()
    print(f"Done. DB: {db_path}")


def _create_team_metadata(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS team_metadata")
    con.execute("""
        CREATE TABLE team_metadata (
            fifa_code        TEXT PRIMARY KEY,
            confederation    TEXT NOT NULL,
            fifa_rank        INTEGER,
            wc_titles        INTEGER DEFAULT 0,
            wc_appearances   INTEGER DEFAULT 0,
            best_finish      TEXT
        )
    """)
    con.executemany(
        "INSERT INTO team_metadata VALUES (?,?,?,?,?,?)",
        TEAM_METADATA,
    )
    print(f"  team_metadata: {len(TEAM_METADATA)} rows")


SQUAD_SIZE = 26  # proxy squad size for nationality-based teams


def _create_players_table(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS players")
    con.execute("""
        CREATE TABLE players (
            player_id            INTEGER PRIMARY KEY,
            short_name           TEXT NOT NULL,
            long_name            TEXT,
            fifa_code            TEXT,
            nationality_name     TEXT,
            nation_team_id       INTEGER,
            nation_position      TEXT,
            nation_jersey_number INTEGER,
            overall              INTEGER,
            potential            INTEGER,
            age                  INTEGER,
            player_positions     TEXT,
            pace                 INTEGER,
            shooting             INTEGER,
            passing              INTEGER,
            dribbling            INTEGER,
            defending            INTEGER,
            physic               INTEGER,
            squad_source         TEXT     -- 'fc26_squad' | 'fc26_nationality'
        )
    """)


def _ingest_fc26_players(con: sqlite3.Connection, csv_path: Path) -> None:
    wc_codes = {row[0] for row in con.execute("SELECT fifa_code FROM teams WHERE NOT is_placeholder")}

    # Nations whose players carry an official nation_team_id in FC26
    squad_nations = {
        "Argentina", "Croatia", "England", "France", "Germany", "Ghana",
        "Mexico", "Morocco", "Netherlands", "Norway", "Portugal", "Qatar",
        "Scotland", "Spain", "United States",
    }

    def _int(v: str) -> int | None:
        return int(v) if v.strip() else None

    # ── Pass 1: official FC26 squads (nation_team_id set) ─────────────────────
    official: dict[str, list[dict]] = {}
    # ── Pass 2 buffer: top players by nationality for proxy squads ────────────
    nationality_pool: dict[str, list[dict]] = {}

    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fc26_name = row["nationality_name"]
            fifa_code = FC26_NAME_TO_CODE.get(fc26_name)
            if not fifa_code or fifa_code not in wc_codes:
                continue

            overall = _int(row["overall"]) or 0
            parsed = {
                "player_id":            _int(row["player_id"]),
                "short_name":           row["short_name"],
                "long_name":            row["long_name"],
                "fifa_code":            fifa_code,
                "nationality_name":     fc26_name,
                "nation_team_id":       _int(row["nation_team_id"]),
                "nation_position":      row["nation_position"] or None,
                "nation_jersey_number": _int(row["nation_jersey_number"]),
                "overall":              overall,
                "potential":            _int(row["potential"]),
                "age":                  _int(row["age"]),
                "player_positions":     row["player_positions"],
                "pace":                 _int(row["pace"]),
                "shooting":             _int(row["shooting"]),
                "passing":              _int(row["passing"]),
                "dribbling":            _int(row["dribbling"]),
                "defending":            _int(row["defending"]),
                "physic":               _int(row["physic"]),
            }

            if row["nation_team_id"] and fc26_name in squad_nations:
                official.setdefault(fifa_code, []).append(parsed)
            elif fc26_name not in squad_nations:
                nationality_pool.setdefault(fifa_code, []).append(parsed)

    def _insert(players: list[dict], source: str) -> int:
        count = 0
        for p in players:
            con.execute(
                "INSERT OR REPLACE INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["player_id"], p["short_name"], p["long_name"], p["fifa_code"],
                 p["nationality_name"], p["nation_team_id"], p["nation_position"],
                 p["nation_jersey_number"], p["overall"], p["potential"], p["age"],
                 p["player_positions"], p["pace"], p["shooting"], p["passing"],
                 p["dribbling"], p["defending"], p["physic"], source),
            )
            count += 1
        return count

    squad_count = sum(
        _insert(players, "fc26_squad") for players in official.values()
    )

    proxy_count = 0
    for fifa_code, pool in nationality_pool.items():
        top26 = sorted(pool, key=lambda p: p["overall"] or 0, reverse=True)[:SQUAD_SIZE]
        proxy_count += _insert(top26, "fc26_nationality")

    print(f"  players: {squad_count} from FC26 squads, {proxy_count} from nationality proxy")


def _create_team_quality_table(con: sqlite3.Connection) -> None:
    """
    Materialized table combining FC26 squad stats (where available) with
    FIFA-rank-based estimates for teams not in the FC26 dataset.

    quality_score: 0.0–1.0 used by TeamStrengthScorer
      - FC26 teams: derived from top-11 average overall (65→0.0, 90→1.0)
      - Rank-only teams: derived from FIFA rank (1→1.0, 48→0.0)
    data_source: 'fc26' | 'fifa_rank'
    """
    con.execute("DROP TABLE IF EXISTS team_quality")
    con.execute("DROP VIEW IF EXISTS team_quality")
    con.execute("""
        CREATE TABLE team_quality (
            fifa_code          TEXT PRIMARY KEY,
            squad_size         INTEGER,
            avg_overall        REAL,
            top_player_rating  INTEGER,
            avg_potential      REAL,
            top11_avg          REAL,
            stars_85plus       INTEGER,
            stars_80plus       INTEGER,
            quality_score      REAL NOT NULL,
            data_source        TEXT NOT NULL
        )
    """)

    FC26_MIN, FC26_MAX = 65.0, 90.0
    RANK_MAX = 48

    # ── FC26-based rows ────────────────────────────────────────────────────────
    fc26_rows = con.execute("""
        SELECT
            p.fifa_code,
            COUNT(*)                                                        AS squad_size,
            ROUND(AVG(p.overall), 1)                                        AS avg_overall,
            MAX(p.overall)                                                  AS top_player_rating,
            ROUND(AVG(p.potential), 1)                                      AS avg_potential,
            (SELECT ROUND(AVG(overall), 1)
             FROM (SELECT overall FROM players p2
                   WHERE p2.fifa_code = p.fifa_code
                   ORDER BY overall DESC LIMIT 11))                         AS top11_avg,
            SUM(CASE WHEN p.overall >= 85 THEN 1 ELSE 0 END)               AS stars_85plus,
            SUM(CASE WHEN p.overall >= 80 THEN 1 ELSE 0 END)               AS stars_80plus
        FROM players p
        WHERE p.fifa_code IS NOT NULL
        GROUP BY p.fifa_code
    """).fetchall()

    fc26_codes: set[str] = set()
    for r in fc26_rows:
        top11 = r["top11_avg"] or FC26_MIN
        score = max(0.0, min(1.0, (top11 - FC26_MIN) / (FC26_MAX - FC26_MIN)))
        con.execute(
            "INSERT INTO team_quality VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["fifa_code"], r["squad_size"], r["avg_overall"], r["top_player_rating"],
             r["avg_potential"], r["top11_avg"], r["stars_85plus"], r["stars_80plus"],
             round(score, 4), "fc26"),
        )
        fc26_codes.add(r["fifa_code"])

    # ── Rank-based rows for WC teams without FC26 squad data ──────────────────
    rank_rows = con.execute("""
        SELECT tm.fifa_code, tm.fifa_rank
        FROM team_metadata tm
        JOIN teams t ON tm.fifa_code = t.fifa_code
        WHERE t.is_placeholder = 0
          AND tm.fifa_rank IS NOT NULL
          AND tm.fifa_code NOT IN ({})
    """.format(",".join(f"'{c}'" for c in fc26_codes))).fetchall()

    for r in rank_rows:
        score = max(0.0, (RANK_MAX - r["fifa_rank"]) / (RANK_MAX - 1))
        con.execute(
            "INSERT INTO team_quality VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["fifa_code"], None, None, None, None, None, None, None,
             round(score, 4), "fifa_rank"),
        )

    total = con.execute("SELECT COUNT(*) FROM team_quality").fetchone()[0]
    fc26_count = len(fc26_codes)
    print(f"  team_quality: {total} teams ({fc26_count} from FC26, {total - fc26_count} from FIFA rank)")


# ── Historical team name → FIFA code ──────────────────────────────────────────
HIST_NAME_TO_CODE: dict[str, str] = {
    "Algeria":               "ALG",
    "Argentina":             "ARG",
    "Australia":             "AUS",
    "Austria":               "AUT",
    "Belgium":               "BEL",
    "Bolivia":               "BOL",
    "Bosnia and Herzegovina":"BIH",
    "Brazil":                "BRA",
    "Bulgaria":              "BUL",
    "Cameroon":              "CMR",
    "Canada":                "CAN",
    "Chile":                 "CHI",
    "China PR":              "CHN",
    "Colombia":              "COL",
    "Costa Rica":            "CRI",
    "Croatia":               "CRO",
    "Cuba":                  "CUB",
    "Czech Republic":        "CZE",
    "Czechoslovakia":        "TCH",
    "Côte d'Ivoire":         "CIV",
    "Denmark":               "DEN",
    "Dutch East Indies":     "DEI",
    "Ecuador":               "ECU",
    "Egypt":                 "EGY",
    "El Salvador":           "SLV",
    "England":               "ENG",
    "FR Yugoslavia":         "YUG",
    "France":                "FRA",
    "Germany":               "GER",
    "Germany DR":            "GDR",
    "Ghana":                 "GHA",
    "Greece":                "GRE",
    "Haiti":                 "HAI",
    "Honduras":              "HND",
    "Hungary":               "HUN",
    "IR Iran":               "IRN",
    "Iceland":               "ISL",
    "Iraq":                  "IRQ",
    "Israel":                "ISR",
    "Italy":                 "ITA",
    "Jamaica":               "JAM",
    "Japan":                 "JPN",
    "Korea DPR":             "PRK",
    "Korea Republic":        "KOR",
    "Kuwait":                "KUW",
    "Mexico":                "MEX",
    "Morocco":               "MAR",
    "Netherlands":           "NED",
    "New Zealand":           "NZL",
    "Nigeria":               "NGA",
    "Northern Ireland":      "NIR",
    "Norway":                "NOR",
    "Panama":                "PAN",
    "Paraguay":              "PAR",
    "Peru":                  "PER",
    "Poland":                "POL",
    "Portugal":              "POR",
    "Qatar":                 "QAT",
    "Republic of Ireland":   "IRL",
    "Romania":               "ROU",
    "Russia":                "RUS",
    "Saudi Arabia":          "KSA",
    "Scotland":              "SCO",
    "Senegal":               "SEN",
    "Serbia":                "SRB",
    "Serbia and Montenegro": "SCG",
    "Slovakia":              "SVK",
    "Slovenia":              "SVN",
    "South Africa":          "RSA",
    "Soviet Union":          "URS",
    "Spain":                 "ESP",
    "Sweden":                "SWE",
    "Switzerland":           "SUI",
    "Togo":                  "TOG",
    "Trinidad and Tobago":   "TRI",
    "Tunisia":               "TUN",
    "Türkiye":               "TUR",
    "Ukraine":               "UKR",
    "United Arab Emirates":  "UAE",
    "United States":         "USA",
    "Uruguay":               "URU",
    "Wales":                 "WAL",
    "West Germany":          "GER",   # unified under GER
    "Yugoslavia":            "YUG",
    "Zaire":                 "COD",
    "Angola":                "ANG",
}

_INTL_NAME_TO_CODE: dict[str, str] = {**HIST_NAME_TO_CODE, **{
    # Additions/corrections for the martj42 dataset naming
    "Iran":                  "IRN",
    "South Korea":           "KOR",
    "North Korea":           "PRK",
    "Turkey":                "TUR",
    "Republic of Ireland":   "IRL",
    "Ivory Coast":           "CIV",
    "Cape Verde":            "CPV",
    "Curacao":               "CUR",
    "Palestine":             "PLE",
    "Kosovo":                "KOS",
}}

# Cut-off: only keep recent matches for form calculation
_FORM_CUTOFF = "2023-01-01"
_WC_CUTOFF   = "2026-06-10"   # day before WC 2026 starts


def _ingest_intl_results(
    con: sqlite3.Connection,
    results_csv: Path,
    scorers_csv: Path,
) -> None:
    con.execute("DROP TABLE IF EXISTS wc_team_history")  # removed; data lives in team_metadata
    # ── team_form: last N competitive + friendly results per team ─────────────
    con.execute("DROP TABLE IF EXISTS team_form")
    con.execute("""
        CREATE TABLE team_form (
            fifa_code       TEXT NOT NULL,
            match_date      TEXT NOT NULL,
            opponent_code   TEXT,
            is_home         INTEGER,
            goals_for       INTEGER,
            goals_against   INTEGER,
            result          TEXT,        -- 'W' | 'D' | 'L'
            tournament      TEXT,
            is_competitive  INTEGER      -- 1 if not a friendly
        )
    """)

    # ── all_h2h: full head-to-head across all competitions ────────────────────
    con.execute("DROP TABLE IF EXISTS all_h2h")
    con.execute("""
        CREATE TABLE all_h2h (
            team_a          TEXT NOT NULL,
            team_b          TEXT NOT NULL,
            matches         INTEGER DEFAULT 0,
            a_wins          INTEGER DEFAULT 0,
            draws           INTEGER DEFAULT 0,
            b_wins          INTEGER DEFAULT 0,
            a_goals         INTEGER DEFAULT 0,
            b_goals         INTEGER DEFAULT 0,
            PRIMARY KEY (team_a, team_b)
        )
    """)

    wc_codes = {row[0] for row in con.execute("SELECT fifa_code FROM teams WHERE NOT is_placeholder")}

    form_rows: list[tuple] = []
    all_h2h:   dict[tuple[str, str], dict] = defaultdict(lambda: {"matches":0,"a_wins":0,"draws":0,"b_wins":0,"a_goals":0,"b_goals":0})
    wc_h2h:    dict[tuple[str, str], dict] = defaultdict(lambda: {"matches":0,"a_wins":0,"draws":0,"b_wins":0,"a_goals":0,"b_goals":0})

    wc_appearances: dict[str, set] = defaultdict(set)

    with open(results_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            date       = row["date"]
            tournament = row["tournament"]
            hname      = row["home_team"]
            aname      = row["away_team"]
            hcode      = _INTL_NAME_TO_CODE.get(hname)
            acode      = _INTL_NAME_TO_CODE.get(aname)
            if not hcode or not acode:
                continue

            is_wc = (tournament == "FIFA World Cup")

            # Skip future WC 2026 matches (NA scores) and anything past cutoff
            if date >= _WC_CUTOFF:
                continue
            try:
                hs  = int(row["home_score"])
                as_ = int(row["away_score"])
            except (ValueError, TypeError):
                continue  # NA or missing score

            is_competitive = 0 if tournament.lower() == "friendly" else 1

            def _update_h2h(store, hc, ac, hs, as_):
                key = (min(hc, ac), max(hc, ac))
                rec = store[key]
                rec["matches"] += 1
                if hc == key[0]:
                    rec["a_goals"] += hs; rec["b_goals"] += as_
                    if hs > as_:   rec["a_wins"] += 1
                    elif hs < as_: rec["b_wins"] += 1
                    else:          rec["draws"]  += 1
                else:
                    rec["a_goals"] += as_; rec["b_goals"] += hs
                    if as_ > hs:   rec["a_wins"] += 1
                    elif as_ < hs: rec["b_wins"] += 1
                    else:          rec["draws"]  += 1

            _update_h2h(all_h2h, hcode, acode, hs, as_)

            if is_wc:
                _update_h2h(wc_h2h, hcode, acode, hs, as_)
                year = int(date[:4])
                for code in (hcode, acode):
                    wc_appearances[code].add(year)

            # Recent form (WC teams only, since cutoff)
            if date >= _FORM_CUTOFF:
                for code, gf, ga, home_flag in ((hcode,hs,as_,1),(acode,as_,hs,0)):
                    if code not in wc_codes:
                        continue
                    result = "W" if gf>ga else ("L" if gf<ga else "D")
                    opp = acode if home_flag else hcode
                    form_rows.append((code, date, opp, home_flag, gf, ga,
                                      result, tournament, is_competitive))

    # ── wc_h2h ────────────────────────────────────────────────────────────────
    con.execute("DROP TABLE IF EXISTS wc_h2h")
    con.execute("""
        CREATE TABLE wc_h2h (
            team_a TEXT NOT NULL, team_b TEXT NOT NULL,
            matches INTEGER DEFAULT 0, a_wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,  b_wins INTEGER DEFAULT 0,
            a_goals INTEGER DEFAULT 0, b_goals INTEGER DEFAULT 0,
            PRIMARY KEY (team_a, team_b)
        )
    """)
    wc_h2h_rows = [(a,b,v["matches"],v["a_wins"],v["draws"],v["b_wins"],v["a_goals"],v["b_goals"])
                   for (a,b),v in wc_h2h.items()]
    con.executemany("INSERT INTO wc_h2h VALUES (?,?,?,?,?,?,?,?)", wc_h2h_rows)

    # ── Update team_metadata.wc_appearances from martj42 match data ─────────
    for code, years in wc_appearances.items():
        con.execute("UPDATE team_metadata SET wc_appearances=? WHERE fifa_code=?",
                    (len(years), code))

    # ── all_h2h ────────────────────────────────────────────────────────────────
    all_h2h_rows = [(a,b,v["matches"],v["a_wins"],v["draws"],v["b_wins"],v["a_goals"],v["b_goals"])
                    for (a,b),v in all_h2h.items()]
    con.executemany("INSERT INTO all_h2h VALUES (?,?,?,?,?,?,?,?)", all_h2h_rows)

    con.executemany("INSERT INTO team_form VALUES (?,?,?,?,?,?,?,?,?)", form_rows)

    print(f"  wc_h2h: {len(wc_h2h_rows)} pairs (from martj42 FIFA World Cup matches)")
    print(f"  team_metadata: wc_appearances updated for {len(wc_appearances)} teams")
    print(f"  all_h2h: {len(all_h2h_rows)} pairs")
    print(f"  team_form: {len(form_rows)} rows (since {_FORM_CUTOFF})")

    # ── player_intl_goals: goal tally per player in international football ────
    con.execute("DROP TABLE IF EXISTS player_intl_goals")
    con.execute("""
        CREATE TABLE player_intl_goals (
            scorer          TEXT NOT NULL,
            team_code       TEXT,
            total_goals     INTEGER DEFAULT 0,
            wc_goals        INTEGER DEFAULT 0,
            own_goals       INTEGER DEFAULT 0,
            penalties       INTEGER DEFAULT 0,
            PRIMARY KEY (scorer, team_code)
        )
    """)

    # {(scorer, team_code): {total, wc, og, pen}}
    goal_tally: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"total": 0, "wc": 0, "og": 0, "pen": 0}
    )

    with open(scorers_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            scorer   = row["scorer"].strip()
            team_name = row["team"].strip()
            if not scorer:
                continue
            tcode = _INTL_NAME_TO_CODE.get(team_name)
            key   = (scorer, tcode or team_name)
            t     = goal_tally[key]
            t["total"] += 1
            if row.get("own_goal", "").upper() == "TRUE":
                t["og"] += 1
            if row.get("penalty", "").upper() == "TRUE":
                t["pen"] += 1
            # Detect WC goals via the scorers being in the wc_history matches file
            # (approximation: we'll refine later; for now mark all as 0)

    con.executemany(
        "INSERT INTO player_intl_goals VALUES (?,?,?,?,?,?)",
        [(k[0], k[1], v["total"], v["wc"], v["og"], v["pen"])
         for k, v in goal_tally.items()],
    )
    print(f"  player_intl_goals: {len(goal_tally)} scorer records")


# ── Playoff winner resolution ──────────────────────────────────────────────────
# Placeholder code → (real_fifa_code, real_name, confederation, fifa_rank)
# UEFA path assignments are best-effort based on WC 2026 qualification draw pots.
# FIFA playoff winners are intercontinental play-off results.
# NOTE: verify group assignments if draw details change.
# Confirmed groups: https://es.uefa.com/european-qualifiers/news/02a0-1f5b6ed60d45-6158c7bfa1ce-1000/
_PLACEHOLDER_RESOLUTION: dict[str, tuple] = {
    "UEPD": ("CZE", "Czech Republic",         "UEFA",     34),  # Group A (was wrongly SWE in Kaggle DB)
    "UEPA": ("BIH", "Bosnia and Herzegovina", "UEFA",     33),  # Group B
    "UEPC": ("TUR", "Turkey",                 "UEFA",     27),  # Group D
    "UEPB": ("SWE", "Sweden",                 "UEFA",     28),  # Group F (was wrongly CZE in Kaggle DB)
    "FP02": ("IRQ", "Iraq",                   "AFC",      60),  # Group I
    "FP01": ("COD", "DR Congo",               "CAF",      55),  # Group K
}


def _resolve_placeholders(con: sqlite3.Connection) -> None:
    for old_code, (new_code, name, conf, rank) in _PLACEHOLDER_RESOLUTION.items():
        # Update teams table
        con.execute("""
            UPDATE teams SET fifa_code = ?, team_name = ?, is_placeholder = 0
            WHERE fifa_code = ?
        """, (new_code, name, old_code))

        # Insert team_metadata if missing
        con.execute("""
            INSERT OR IGNORE INTO team_metadata (fifa_code, confederation, fifa_rank, wc_titles, wc_appearances)
            VALUES (?, ?, ?, 0, 0)
        """, (new_code, conf, rank))

        # Update players that were ingested under old code (none expected, but safe)
        con.execute("UPDATE players SET fifa_code = ? WHERE fifa_code = ?", (new_code, old_code))

        # Update team_quality if present
        con.execute("UPDATE team_quality SET fifa_code = ? WHERE fifa_code = ?", (new_code, old_code))

    # Insert FC26-or-rank quality for newly resolved teams that have no quality row yet
    RANK_MAX = 48
    for old_code, (new_code, name, conf, rank) in _PLACEHOLDER_RESOLUTION.items():
        exists = con.execute(
            "SELECT 1 FROM team_quality WHERE fifa_code = ?", (new_code,)
        ).fetchone()
        if not exists:
            score = round(max(0.0, (RANK_MAX - rank) / (RANK_MAX - 1)), 4)
            con.execute(
                "INSERT INTO team_quality VALUES (?,?,?,?,?,?,?,?,?,?)",
                (new_code, None, None, None, None, None, None, None, score, "fifa_rank"),
            )

    # Rebuild wc_h2h and all_h2h references from historical name → new code
    con.execute("UPDATE wc_h2h SET team_a = 'SWE' WHERE team_a = 'SWE'")  # already correct
    # TUR might appear as "Turkey" in old data — already mapped in HIST_NAME_TO_CODE as TUR
    # BIH → "Bosnia and Herzegovina" already maps to BIH in HIST_NAME_TO_CODE
    # CZE → "Czech Republic" already maps to CZE
    # No wc_h2h entries expected for IRQ/COD under old placeholder codes

    resolved = len(_PLACEHOLDER_RESOLUTION)
    print(f"  placeholders resolved: {resolved} teams updated")


if __name__ == "__main__":
    build()
