"""
Strava data fetcher.
Credentials are loaded from .streamlit/secrets.toml (locally) or
Streamlit Cloud Secrets (in production) — never hardcoded.
"""

import os
import requests
import time


# ── Credentials ────────────────────────────────────────────────────────────────
def _secrets():
    try:
        import streamlit as st
        return st.secrets
    except Exception:
        return {}

def _get(key: str) -> str:
    s = _secrets()
    return s.get(key) or os.environ.get(key, "")


def get_access_token() -> str:
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id":     _get("STRAVA_CLIENT_ID"),
            "client_secret": _get("STRAVA_CLIENT_SECRET"),
            "grant_type":    "refresh_token",
            "refresh_token": _get("STRAVA_REFRESH_TOKEN"),
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]


# ── Fetch ──────────────────────────────────────────────────────────────────────
def get_all_activities(access_token: str, after_ts: int | None = None) -> list:
    """
    Fetch activities from Strava.
    Pass after_ts (Unix int) to fetch only activities newer than that timestamp.
    """
    page, per_page, activities = 1, 100, []

    while True:
        params = {"per_page": per_page, "page": page}
        if after_ts:
            params["after"] = int(after_ts)

        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 900))
            print(f"Rate limit hit — waiting {retry_after}s…")
            time.sleep(retry_after)
            continue

        response.raise_for_status()
        print(f"Rate usage: {response.headers.get('X-RateLimit-Usage', '?')}")

        data = response.json()
        if not data:
            break

        activities.extend(data)
        print(f"Fetched page {page} ({len(data)} activities)")
        page += 1
        time.sleep(1.2)

    return activities


# ── CLI entry-point (full historical load) ─────────────────────────────────────
if __name__ == "__main__":
    from db import save_runs

    try:
        print("Getting access token…")
        token = get_access_token()
        print("Fetching all activities…")
        activities = get_all_activities(token)
        saved = save_runs(activities)
        print(f"Done — {saved} runs saved to Supabase.")
    except Exception as e:
        print(f"Error: {e}")
