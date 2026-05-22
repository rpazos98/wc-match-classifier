"""
Read-only queries against wc2026.db.
Returns plain dataclasses / dicts — no SQLite Row leakage into the rest of the app.
"""
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from classifier.models import Match, Squad, Stage

DB_PATH = Path(__file__).parent.parent / "data" / "wc2026.db"

# ── Stage name → enum mapping ──────────────────────────────────────────────────
_STAGE_MAP: dict[str, Stage] = {
    "Group Stage":          Stage.GROUP,
    "Round of 32":          Stage.R32,
    "Round of 16":          Stage.R16,
    "Quarterfinals":        Stage.QF,
    "Semifinals":           Stage.SF,
    "Third Place Playoff":  Stage.THIRD,
    "Final":                Stage.FINAL,
}


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── Matches ────────────────────────────────────────────────────────────────────

def load_matches() -> list[Match]:
    con = _connect()
    rows = con.execute("""
        SELECT
            m.id,
            m.match_number,
            ht.fifa_code  AS home_code,
            at.fifa_code  AS away_code,
            m.kickoff_at,
            ts.stage_name,
            c.venue_name,
            c.city_name,
            c.country
        FROM matches m
        LEFT JOIN teams             ht ON m.home_team_id = ht.id
        LEFT JOIN teams             at ON m.away_team_id = at.id
        JOIN host_cities             c ON m.city_id      = c.id
        JOIN tournament_stages      ts ON m.stage_id     = ts.id
        ORDER BY m.match_number
    """).fetchall()

    squads = _load_squads(con)
    con.close()

    matches: list[Match] = []
    for r in rows:
        home = r["home_code"] or "TBD"
        away = r["away_code"] or "TBD"
        stage = _STAGE_MAP[r["stage_name"]]
        venue = f"{r['venue_name']}, {r['city_name']}"
        kickoff = _parse_kickoff(r["kickoff_at"])

        match_id = f"M{r['match_number']:03d}"
        matches.append(Match(
            match_id=match_id,
            home=home,
            away=away,
            kickoff_utc=kickoff,
            stage=stage,
            venue=venue,
            home_squad=squads.get(home),
            away_squad=squads.get(away),
        ))
    return matches


def _parse_kickoff(raw: str) -> datetime:
    """Parse '2026-06-11 15:00:00-06' → UTC datetime."""
    # Python fromisoformat handles offset-aware strings in 3.11+
    # For 3.9/3.10 compat, normalise the offset format
    normalised = raw.replace(" ", "T")
    if len(normalised) == 22:          # e.g. -06 → needs :00
        normalised = normalised[:-3] + normalised[-3:] + ":00"
    dt = datetime.fromisoformat(normalised)
    return dt.astimezone(timezone.utc).replace(tzinfo=timezone.utc)


def _load_squads(con: sqlite3.Connection) -> dict[str, Squad]:
    rows = con.execute("""
        SELECT fifa_code, short_name
        FROM players
        WHERE fifa_code IS NOT NULL
        ORDER BY fifa_code, overall DESC
    """).fetchall()

    teams: dict[str, list[str]] = {}
    for r in rows:
        teams.setdefault(r["fifa_code"], []).append(r["short_name"])

    return {code: Squad(code, tuple(players)) for code, players in teams.items()}


# ── Team quality (for scoring) ─────────────────────────────────────────────────

def team_quality_scores() -> dict[str, float]:
    """Returns {fifa_code: quality_score 0.0–1.0} from the materialized team_quality table."""
    con = _connect()
    rows = con.execute("SELECT fifa_code, quality_score FROM team_quality").fetchall()
    con.close()
    return {r["fifa_code"]: r["quality_score"] for r in rows}


# ── Players per team (for user profile matching) ───────────────────────────────

def players_by_team() -> dict[str, list[str]]:
    """Returns {fifa_code: [player_short_name, ...]} sorted by overall desc."""
    con = _connect()
    rows = con.execute("""
        SELECT fifa_code, short_name
        FROM players
        WHERE fifa_code IS NOT NULL
        ORDER BY fifa_code, overall DESC
    """).fetchall()
    con.close()

    result: dict[str, list[str]] = {}
    for r in rows:
        result.setdefault(r["fifa_code"], []).append(r["short_name"])
    return result


# ── H2H rivalry scores ────────────────────────────────────────────────────────

def wc_h2h_scores() -> dict[frozenset, float]:
    """
    Returns {frozenset({a, b}): rivalry_score 0.0–1.0}.

    Score combines:
      - encounter frequency  (more WC meetings = higher base)
      - competitiveness      (50/50 win rate = max, lopsided = lower)
    """
    con = _connect()
    rows = con.execute(
        "SELECT team_a, team_b, matches, a_wins, draws, b_wins FROM wc_h2h"
    ).fetchall()
    con.close()

    result: dict[frozenset, float] = {}
    for r in rows:
        total = r["matches"]
        if total == 0:
            continue
        # Frequency component: log-scaled, capped at 7 meetings → 1.0
        import math
        freq = min(1.0, math.log1p(total) / math.log1p(7))

        # Competitiveness: 1.0 when 50/50, 0.0 when completely one-sided
        decisive = r["a_wins"] + r["b_wins"]
        if decisive == 0:
            competitiveness = 0.5
        else:
            win_rate = r["a_wins"] / decisive
            competitiveness = 1.0 - abs(win_rate - 0.5) * 2  # 0.5→1.0, 0/1→0.0

        score = 0.6 * freq + 0.4 * competitiveness
        result[frozenset({r["team_a"], r["team_b"]})] = score

    return result


# ── All-competition H2H scores ────────────────────────────────────────────────

def all_h2h_scores() -> dict[frozenset, float]:
    """Same formula as wc_h2h_scores() but from all_h2h. Frequency cap raised for larger counts."""
    con = _connect()
    rows = con.execute(
        "SELECT team_a, team_b, matches, a_wins, draws, b_wins FROM all_h2h"
    ).fetchall()
    con.close()

    result: dict[frozenset, float] = {}
    for r in rows:
        total = r["matches"]
        if total == 0:
            continue
        freq = min(1.0, math.log1p(total) / math.log1p(50))  # cap at 50 meetings

        decisive = r["a_wins"] + r["b_wins"]
        if decisive == 0:
            competitiveness = 0.5
        else:
            win_rate = r["a_wins"] / decisive
            competitiveness = 1.0 - abs(win_rate - 0.5) * 2

        result[frozenset({r["team_a"], r["team_b"]})] = 0.6 * freq + 0.4 * competitiveness

    return result


# ── WC rivals (3+ WC meetings) ─────────────────────────────────────────────────

def wc_rivals(min_meetings: int = 3) -> dict[str, set[str]]:
    """Returns {fifa_code: {rival_codes}} for teams with >= min_meetings WC encounters."""
    con = _connect()
    rows = con.execute(
        "SELECT team_a, team_b FROM wc_h2h WHERE matches >= ?", (min_meetings,)
    ).fetchall()
    con.close()

    result: dict[str, set[str]] = {}
    for r in rows:
        result.setdefault(r["team_a"], set()).add(r["team_b"])
        result.setdefault(r["team_b"], set()).add(r["team_a"])
    return result


# ── Dark horse teams ───────────────────────────────────────────────────────────

def dark_horse_teams(threshold: float = 0.15) -> set[str]:
    """
    Returns FIFA codes of teams whose FC26 quality_score exceeds their
    rank-implied score by > threshold — teams punching above their ranking.
    """
    con = _connect()
    rows = con.execute("""
        SELECT tq.fifa_code,
               tq.quality_score - MAX(0.0, (48.0 - tm.fifa_rank) / 47.0) AS gap
        FROM team_quality tq
        JOIN team_metadata tm USING(fifa_code)
        WHERE tm.fifa_rank IS NOT NULL
    """).fetchall()
    con.close()
    return {r["fifa_code"] for r in rows if r["gap"] > threshold}


# ── Confederation map ──────────────────────────────────────────────────────────

def confederation_map() -> dict[str, str]:
    """Returns {fifa_code: confederation}."""
    con = _connect()
    rows = con.execute("SELECT fifa_code, confederation FROM team_metadata").fetchall()
    con.close()
    return {r["fifa_code"]: r["confederation"] for r in rows}


# ── Player goals ───────────────────────────────────────────────────────────────

def player_goals_map() -> dict[str, int]:
    """Returns {scorer_full_name: total_goals} from player_intl_goals."""
    con = _connect()
    rows = con.execute(
        "SELECT scorer, total_goals FROM player_intl_goals WHERE total_goals > 0"
    ).fetchall()
    con.close()
    return {r["scorer"]: r["total_goals"] for r in rows}


def player_overall_ratings() -> dict[str, int]:
    """Returns {short_name: overall} for all WC squad players that have a rating."""
    con = _connect()
    rows = con.execute(
        "SELECT short_name, overall FROM players WHERE fifa_code IS NOT NULL AND overall IS NOT NULL"
    ).fetchall()
    con.close()
    return {r["short_name"]: r["overall"] for r in rows}


def player_long_names() -> dict[str, str]:
    """Returns {short_name: long_name} from players table."""
    con = _connect()
    rows = con.execute(
        "SELECT short_name, long_name FROM players WHERE long_name IS NOT NULL"
    ).fetchall()
    con.close()
    return {r["short_name"]: r["long_name"] for r in rows}


# ── Teams ──────────────────────────────────────────────────────────────────────

def team_group_map() -> dict[str, str]:
    """Returns {fifa_code: group_letter} for all non-placeholder teams."""
    con  = _connect()
    rows = con.execute(
        "SELECT fifa_code, group_letter FROM teams WHERE is_placeholder = 0 AND group_letter IS NOT NULL"
    ).fetchall()
    con.close()
    return {r["fifa_code"]: r["group_letter"] for r in rows}


def team_attack_scores() -> dict[str, float]:
    """Returns {fifa_code: attack_score 0.0-1.0} based on avg shooting of top 11 players."""
    con = _connect()
    rows = con.execute("""
        WITH ranked AS (
            SELECT fifa_code, shooting,
                   ROW_NUMBER() OVER (PARTITION BY fifa_code ORDER BY overall DESC) AS rn
            FROM players
            WHERE fifa_code IS NOT NULL
        )
        SELECT fifa_code, AVG(shooting) / 99.0 AS attack_score
        FROM ranked
        WHERE rn <= 11
        GROUP BY fifa_code
    """).fetchall()
    con.close()
    return {r["fifa_code"]: r["attack_score"] for r in rows}


def group_match_matchdays() -> dict[int, int]:
    """
    Returns {match_number: matchday (1|2|3)} for all group stage matches.
    Matchday is determined by kickoff order within each group (first 2 = MD1, next 2 = MD2, last 2 = MD3).
    """
    con = _connect()
    rows = con.execute("""
        WITH grp_matches AS (
            SELECT m.match_number,
                   ROW_NUMBER() OVER (
                       PARTITION BY ht.group_letter
                       ORDER BY m.kickoff_at
                   ) AS rn
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN tournament_stages ts ON m.stage_id = ts.id
            WHERE ts.stage_name = 'Group Stage'
              AND ht.group_letter IS NOT NULL
        )
        SELECT match_number,
               CASE WHEN rn <= 2 THEN 1 WHEN rn <= 4 THEN 2 ELSE 3 END AS matchday
        FROM grp_matches
    """).fetchall()
    con.close()
    return {r["match_number"]: r["matchday"] for r in rows}


def team_defense_scores() -> dict[str, float]:
    """Returns {fifa_code: defense_score 0.0-1.0} based on avg defending of top 11 players."""
    con = _connect()
    rows = con.execute("""
        WITH ranked AS (
            SELECT fifa_code, defending,
                   ROW_NUMBER() OVER (PARTITION BY fifa_code ORDER BY overall DESC) AS rn
            FROM players
            WHERE fifa_code IS NOT NULL
        )
        SELECT fifa_code, AVG(defending) / 99.0 AS defense_score
        FROM ranked
        WHERE rn <= 11
        GROUP BY fifa_code
    """).fetchall()
    con.close()
    return {r["fifa_code"]: r["defense_score"] for r in rows}


def team_fifa_ranks() -> dict[str, int]:
    """Returns {fifa_code: fifa_rank} for all teams with a known rank."""
    con = _connect()
    rows = con.execute(
        "SELECT fifa_code, fifa_rank FROM team_metadata WHERE fifa_rank IS NOT NULL"
    ).fetchall()
    con.close()
    return {r["fifa_code"]: r["fifa_rank"] for r in rows}


def wc_h2h_meetings() -> dict[frozenset, int]:
    """Returns {frozenset({a, b}): n_wc_meetings} for all WC H2H pairs."""
    con = _connect()
    rows = con.execute("SELECT team_a, team_b, matches FROM wc_h2h").fetchall()
    con.close()
    return {frozenset({r["team_a"], r["team_b"]}): r["matches"] for r in rows}


def wc_h2h_record(team_a: str, team_b: str) -> dict | None:
    """Return full WC H2H record between two teams, or None if never met."""
    con = _connect()
    row = con.execute(
        "SELECT team_a, team_b, matches, a_wins, draws, b_wins "
        "FROM wc_h2h WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)",
        (team_a, team_b, team_b, team_a),
    ).fetchone()
    con.close()
    if not row or row["matches"] == 0:
        return None
    if row["team_a"] == team_a:
        return {"matches": row["matches"], "a_wins": row["a_wins"],
                "draws": row["draws"], "b_wins": row["b_wins"]}
    return {"matches": row["matches"], "a_wins": row["b_wins"],
            "draws": row["draws"], "b_wins": row["a_wins"]}


def all_h2h_record(team_a: str, team_b: str) -> dict | None:
    """Return full all-competition H2H record, or None if never met."""
    con = _connect()
    row = con.execute(
        "SELECT team_a, team_b, matches, a_wins, draws, b_wins "
        "FROM all_h2h WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)",
        (team_a, team_b, team_b, team_a),
    ).fetchone()
    con.close()
    if not row or row["matches"] == 0:
        return None
    if row["team_a"] == team_a:
        return {"matches": row["matches"], "a_wins": row["a_wins"],
                "draws": row["draws"], "b_wins": row["b_wins"]}
    return {"matches": row["matches"], "a_wins": row["b_wins"],
            "draws": row["draws"], "b_wins": row["a_wins"]}


def wc_h2h_drama(team_a: str, team_b: str) -> dict | None:
    """Return WC drama indicators for a pair, or None if no data."""
    con = _connect()
    row = con.execute(
        "SELECT * FROM wc_h2h_drama "
        "WHERE (team_a = ? AND team_b = ?) OR (team_a = ? AND team_b = ?)",
        (team_a, team_b, team_b, team_a),
    ).fetchone()
    con.close()
    if not row:
        return None
    return dict(row)


def wc_drama_scores() -> dict[frozenset, float]:
    """Returns {frozenset({a, b}): drama_score 0.0-1.0} from wc_h2h_drama."""
    con = _connect()
    try:
        rows = con.execute("SELECT team_a, team_b, drama_score FROM wc_h2h_drama").fetchall()
    except Exception:
        con.close()
        return {}
    con.close()
    return {frozenset({r["team_a"], r["team_b"]}): r["drama_score"] for r in rows}


def recent_h2h_matches(team_a: str, team_b: str, n: int = 5) -> list[dict]:
    """Return last N matches between two teams from intl_results CSV."""
    from classifier.elo import _CODE_TO_CSV, _DATA
    import csv

    name_a = _CODE_TO_CSV.get(team_a, team_a)
    name_b = _CODE_TO_CSV.get(team_b, team_b)

    with open(_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    matches = []
    for r in rows:
        if not ((r["home_team"] == name_a and r["away_team"] == name_b) or
                (r["home_team"] == name_b and r["away_team"] == name_a)):
            continue
        try:
            hs = int(float(r["home_score"]))
            as_ = int(float(r["away_score"]))
        except (ValueError, TypeError):
            continue

        # Normalize to team_a perspective
        if r["home_team"] == name_a:
            matches.append({
                "date": r["date"],
                "tournament": r.get("tournament", ""),
                "a_goals": hs,
                "b_goals": as_,
            })
        else:
            matches.append({
                "date": r["date"],
                "tournament": r.get("tournament", ""),
                "a_goals": as_,
                "b_goals": hs,
            })

    return matches[-n:]


def load_teams() -> list[dict]:
    con = _connect()
    rows = con.execute("""
        SELECT
            t.fifa_code,
            t.team_name,
            t.group_letter,
            t.is_placeholder,
            tm.confederation,
            tm.fifa_rank,
            tm.wc_titles,
            tm.wc_appearances,
            tm.best_finish,
            tq.top11_avg,
            tq.stars_85plus
        FROM teams t
        LEFT JOIN team_metadata tm ON t.fifa_code = tm.fifa_code
        LEFT JOIN team_quality   tq ON t.fifa_code = tq.fifa_code
        ORDER BY t.group_letter, t.id
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]
