"""
One-time migration: load strava_activities.csv → Supabase.
Run this once after setting up your Supabase project and secrets.toml:

    python migrate.py
"""

import csv
import sys
import os

CSV_FILE = "strava_activities.csv"

# Load .streamlit/secrets.toml into env so db.py can find credentials
def _load_secrets():
    toml_path = os.path.join(".streamlit", "secrets.toml")
    if not os.path.exists(toml_path):
        print("ERROR: .streamlit/secrets.toml not found.")
        sys.exit(1)
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            # Fallback: simple line parser for key = "value"
            secrets = {}
            with open(toml_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        os.environ[k.strip()] = v.strip().strip('"')
            return
    with open(toml_path, "rb") as f:
        secrets = tomllib.load(f)
    for k, v in secrets.items():
        os.environ[k] = str(v)

_load_secrets()

from db import save_runs  # noqa: E402 — must come after env is set


def csv_row_to_activity(row: dict) -> dict:
    """Convert a CSV row back into a Strava-like activity dict."""
    def num(val):
        try:
            return float(val) if val not in ("", None) else None
        except ValueError:
            return None

    return {
        "id":                   int(row["id"]) if row.get("id") else None,
        "name":                 row.get("name"),
        "start_date":           row.get("start_date"),
        "distance":             num(row.get("distance")),
        "moving_time":          num(row.get("moving_time")),
        "elapsed_time":         num(row.get("elapsed_time")),
        "total_elevation_gain": num(row.get("total_elevation_gain")),
        "elev_high":            num(row.get("elev_high")),
        "elev_low":             num(row.get("elev_low")),
        "sport_type":           row.get("sport_type") or "Run",
        "type":                 row.get("sport_type") or "Run",
        "workout_type":         row.get("workout_type"),
        "average_speed":        num(row.get("average_speed")),
        "max_speed":            num(row.get("max_speed")),
        "average_heartrate":    num(row.get("average_heartrate")),
        "max_heartrate":        num(row.get("max_heartrate")),
        "average_cadence":      num(row.get("average_cadence")),
        "suffer_score":         num(row.get("suffer_score")),
        "kilojoules":           num(row.get("kilojoules")),
        "achievement_count":    num(row.get("achievement_count")),
        "kudos_count":          num(row.get("kudos_count")),
        "gear_id":              row.get("gear_id"),
        "map": {"summary_polyline": row.get("map_summary_polyline", "")},
    }


def main():
    if not os.path.exists(CSV_FILE):
        print(f"ERROR: '{CSV_FILE}' not found.")
        sys.exit(1)

    print(f"Reading {CSV_FILE}…")
    activities = []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("id") and row["id"] not in ("", "null"):
                activities.append(csv_row_to_activity(row))

    print(f"Found {len(activities)} rows. Uploading to Supabase…")
    saved = save_runs(activities)
    print(f"Done — {saved} runs saved to Supabase.")


if __name__ == "__main__":
    main()
