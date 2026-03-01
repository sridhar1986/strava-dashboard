"""
Database layer — Supabase backend.
Works locally (via .streamlit/secrets.toml) and on Streamlit Cloud (via Secrets UI).

Supabase table setup — run this SQL once in the Supabase SQL Editor:

    CREATE TABLE IF NOT EXISTS runs (
        id                  bigint PRIMARY KEY,
        name                text,
        start_date          timestamptz,
        distance            float,
        moving_time         int,
        elapsed_time        int,
        total_elevation_gain float,
        elev_high           float,
        elev_low            float,
        sport_type          text,
        workout_type        text,
        average_speed       float,
        max_speed           float,
        average_heartrate   float,
        max_heartrate       float,
        average_cadence     float,
        suffer_score        float,
        kilojoules          float,
        achievement_count   int,
        kudos_count         int,
        gear_id             text,
        map_summary_polyline text
    );
"""

import os
import pandas as pd
from supabase import create_client, Client

TABLE = "runs"

# ── Client ─────────────────────────────────────────────────────────────────────
def _get_client() -> Client:
    """
    Looks for credentials in (priority order):
      1. st.secrets  (Streamlit Cloud / local secrets.toml)
      2. Environment variables
    """
    try:
        import streamlit as st
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials not found. "
            "Add SUPABASE_URL and SUPABASE_KEY to .streamlit/secrets.toml "
            "or as environment variables."
        )
    return create_client(url, key)


# ── Read ───────────────────────────────────────────────────────────────────────
def load_runs() -> pd.DataFrame:
    """Fetch all runs from Supabase and return as a DataFrame."""
    client = _get_client()
    response = client.table(TABLE).select("*").order("start_date", desc=False).execute()
    rows = response.data

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Coerce numeric columns that Supabase may return as strings
    numeric_cols = [
        "distance", "moving_time", "elapsed_time", "total_elevation_gain",
        "elev_high", "elev_low", "average_speed", "max_speed",
        "average_heartrate", "max_heartrate", "average_cadence",
        "suffer_score", "kilojoules", "achievement_count", "kudos_count",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ── Write ──────────────────────────────────────────────────────────────────────
def save_runs(activities: list) -> int:
    """
    Upsert a list of Strava activity dicts into Supabase.
    Only running activities are saved.
    Returns the number of new/updated rows.
    """
    runs = [
        a for a in activities
        if a.get("sport_type") in ("Run", "VirtualRun")
        or a.get("type") in ("Run", "VirtualRun")
    ]

    if not runs:
        return 0

    client = _get_client()

    rows = []
    for a in runs:
        map_info = a.get("map") or {}
        rows.append({
            "id":                   a.get("id"),
            "name":                 a.get("name"),
            "start_date":           a.get("start_date"),
            "distance":             a.get("distance"),
            "moving_time":          a.get("moving_time"),
            "elapsed_time":         a.get("elapsed_time"),
            "total_elevation_gain": a.get("total_elevation_gain"),
            "elev_high":            a.get("elev_high"),
            "elev_low":             a.get("elev_low"),
            "sport_type":           a.get("sport_type"),
            "workout_type":         a.get("workout_type"),
            "average_speed":        a.get("average_speed"),
            "max_speed":            a.get("max_speed"),
            "average_heartrate":    a.get("average_heartrate"),
            "max_heartrate":        a.get("max_heartrate"),
            "average_cadence":      a.get("average_cadence"),
            "suffer_score":         a.get("suffer_score"),
            "kilojoules":           a.get("kilojoules"),
            "achievement_count":    a.get("achievement_count"),
            "kudos_count":          a.get("kudos_count"),
            "gear_id":              a.get("gear_id"),
            "map_summary_polyline": map_info.get("summary_polyline", ""),
        })

    # Upsert in batches of 500 to stay within Supabase request limits
    batch_size = 500
    total_saved = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table(TABLE).upsert(batch, on_conflict="id").execute()
        total_saved += len(batch)

    return total_saved


# ── Latest timestamp (for incremental sync) ────────────────────────────────────
def get_latest_timestamp() -> int | None:
    """Return Unix timestamp of the most recent run, or None if table is empty."""
    client = _get_client()
    response = (
        client.table(TABLE)
        .select("start_date")
        .order("start_date", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None

    from datetime import datetime, timezone
    raw = response.data[0]["start_date"]
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return int(dt.timestamp())
