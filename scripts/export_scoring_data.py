"""Export scoring data as static JSON for frontend scorers."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "wc2026.db"
OUT_DIR = ROOT / "frontend" / "public" / "data"


def export_team_stars():
    """Export players rated 85+ per team."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT fifa_code, short_name, overall FROM players "
        "WHERE fifa_code IS NOT NULL AND overall >= 85 "
        "ORDER BY fifa_code, overall DESC"
    ).fetchall()
    con.close()

    teams: dict[str, list] = {}
    for code, name, overall in rows:
        teams.setdefault(code, []).append({"name": name, "overall": overall})

    path = OUT_DIR / "team_stars.json"
    path.write_text(json.dumps(teams, indent=2, ensure_ascii=False))
    total = sum(len(v) for v in teams.values())
    print(f"team_stars.json: {len(teams)} teams, {total} stars")


def export_h2h():
    """Export H2H rivalry/drama/meetings data."""
    from db.query import wc_h2h_scores, wc_h2h_meetings, all_h2h_scores, wc_drama_scores

    rivalry = wc_h2h_scores()
    meetings = wc_h2h_meetings()
    all_h2h = all_h2h_scores()
    drama = wc_drama_scores()

    # Collect all pair keys
    all_keys = set(rivalry.keys()) | set(all_h2h.keys()) | set(drama.keys())

    result = {}
    for key in all_keys:
        r = rivalry.get(key, 0.0)
        d = drama.get(key, 0.0)
        a = all_h2h.get(key, 0.0)
        m = meetings.get(key, 0)
        # Skip pairs with no signal
        if r == 0 and d == 0 and a == 0:
            continue
        pair = "-".join(sorted(key))
        result[pair] = {
            "rivalry": round(r, 4),
            "drama": round(d, 4),
            "all_h2h": round(a, 4),
            "meetings": m,
        }

    path = OUT_DIR / "h2h.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"h2h.json: {len(result)} pairs")


def export_matchdays():
    """Export group match matchday assignments."""
    from db.query import group_match_matchdays

    md = group_match_matchdays()
    # Convert int keys to strings for JSON
    result = {str(k): v for k, v in md.items()}

    path = OUT_DIR / "matchdays.json"
    path.write_text(json.dumps(result))
    print(f"matchdays.json: {len(result)} matches")


if __name__ == "__main__":
    export_team_stars()
    export_h2h()
    export_matchdays()
