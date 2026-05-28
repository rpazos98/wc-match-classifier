"""
Pre-compute all match data with a neutral profile (no favorites).

Outputs frontend/public/data/matches.json — loaded by the frontend
at startup for instant display. Personal scorers (Favorite Team,
Same Group, Momento) are computed client-side from raw data + profile.

Usage:
    uv run python scripts/export_matches.py
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from classifier import load_all_matches, classify_matches
from classifier.models import UserProfile
from classifier.learning import DEFAULT_WEIGHTS
from web import _serialize_match, _score_weights
from zoneinfo import ZoneInfo
from db.query import team_group_map


def main():
    profile = UserProfile(name="Neutral", team_affinities={}, time_windows=[])
    tz = ZoneInfo("UTC")

    all_matches = load_all_matches()
    confirmed = [m for m in all_matches if m.home != "TBD" and m.away != "TBD"]
    classed = classify_matches(confirmed, profile)

    matches = []
    for c in classed:
        d = _serialize_match(c, tz)
        # Include group info for client-side Same Group scorer
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

    out_dir = Path(__file__).parent.parent / "frontend" / "public" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "matches.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False))

    print(f"Exported {len(matches)} matches to {out_path}")
    print(f"File size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()