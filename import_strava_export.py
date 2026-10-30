"""
Import Strava bulk-export activities.csv → Supabase.

Strava's data export uses different column names and some duplicate columns
compared to the API. This script handles the mapping correctly.

Usage:
    python import_strava_export.py /path/to/export_XXXXXXXX/activities.csv
"""

import sys
import os
import pandas as pd

# ── Load secrets into env so db.py can connect ─────────────────────────────────
def _load_secrets():
    toml_path = os.path.join(".streamlit", "secrets.toml")
    if not os.path.exists(toml_path):
        print("ERROR: .streamlit/secrets.toml not found. Add your Supabase credentials first.")
        sys.exit(1)
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    with open(toml_path, "rb") as f:
        secrets = tomllib.load(f)
    for k, v in secrets.items():
        os.environ[k] = str(v)

_load_secrets()

from db import save_runs  # noqa: E402 — must come after env is set


# ── Column mapping ─────────────────────────────────────────────────────────────
# The export CSV has duplicate column names; pandas renames them with .1 suffix.
# Distance.1 = meters (what the API returns), Distance = km summary figure.
# Max Heart Rate.1 = per-activity HR, Elapsed Time.1 = detailed elapsed seconds.

EXPORT_TO_API = {
    "Activity ID":        "id",
    "Activity Name":      "name",
    "Activity Type":      "sport_type",
    "Activity Gear":      "gear_id",
    "Moving Time":        "moving_time",       # seconds
    "Elapsed Time.1":     "elapsed_time",       # seconds (detailed column)
    "Distance.1":         "distance",           # metres
    "Max Speed":          "max_speed",          # m/s
    "Average Speed":      "average_speed",      # m/s
    "Elevation Gain":     "total_elevation_gain",  # metres
    "Elevation High":     "elev_high",          # metres
    "Elevation Low":      "elev_low",           # metres
    "Average Cadence":    "average_cadence",    # rpm (×2 = spm in dashboard)
    "Max Heart Rate.1":   "max_heartrate",
    "Average Heart Rate": "average_heartrate",
    "Calories":           "kilojoules",         # kcal ≈ close enough; dashboard doesn't chart it
    "Relative Effort.1":  "suffer_score",
}


def parse_export(csv_path: str) -> list[dict]:
    df = pd.read_csv(csv_path)

    # Keep only running activities
    runs = df[df["Activity Type"].isin(["Run", "VirtualRun"])].copy()
    print(f"  Found {len(runs)} running activities out of {len(df)} total.")

    # Parse date — export format: "Oct 27, 2026, 2:31:26 AM"
    runs["start_date"] = pd.to_datetime(
        df.loc[runs.index, "Activity Date"], format="%b %d, %Y, %I:%M:%S %p", errors="coerce"
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    activities = []
    for _, row in runs.iterrows():
        a = {"start_date": row["start_date"], "type": row.get("Activity Type", "Run")}
        for export_col, api_field in EXPORT_TO_API.items():
            val = row.get(export_col)
            if pd.isna(val) if not isinstance(val, str) else (val == ""):
                a[api_field] = None
            else:
                a[api_field] = val

        # id must be int
        try:
            a["id"] = int(a["id"])
        except (TypeError, ValueError):
            continue  # skip rows without a valid ID

        # Integer fields — Supabase rejects float strings like "3476.0"
        for int_field in ("moving_time", "elapsed_time", "achievement_count", "kudos_count"):
            if a.get(int_field) is not None:
                try:
                    a[int_field] = int(float(a[int_field]))
                except (TypeError, ValueError):
                    a[int_field] = None

        # Strava export cadence is already spm for running; db.py expects rpm (×2 in dashboard)
        # Keep as-is — dashboard multiplies by 2 assuming rpm input
        if a.get("average_cadence"):
            try:
                a["average_cadence"] = float(a["average_cadence"]) / 2
            except (TypeError, ValueError):
                pass

        # map_summary_polyline — not in bulk export
        a["map"] = {"summary_polyline": ""}
        a["workout_type"] = None
        a["achievement_count"] = None
        a["kudos_count"] = None

        activities.append(a)

    return activities


def main():
    if len(sys.argv) < 2:
        # Try the default Downloads path
        default = os.path.expanduser("~/Downloads/export_40245052/activities.csv")
        if os.path.exists(default):
            csv_path = default
            print(f"No path given — using default: {csv_path}")
        else:
            print("Usage: python import_strava_export.py /path/to/activities.csv")
            sys.exit(1)
    else:
        csv_path = sys.argv[1]

    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    print(f"Reading {csv_path} …")
    activities = parse_export(csv_path)
    print(f"  Parsed {len(activities)} runs. Uploading to Supabase…")

    saved = save_runs(activities)
    print(f"  Done — {saved} runs saved to Supabase. ✅")


if __name__ == "__main__":
    main()

