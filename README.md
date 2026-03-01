# 🏃 Strava Run Dashboard

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.54-FF4B4B?logo=streamlit)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase)
![Plotly](https://img.shields.io/badge/Charts-Plotly-3D4DB7?logo=plotly)
![License](https://img.shields.io/badge/License-MIT-green)

A personal running analytics dashboard built with Streamlit, powered by the Strava API and Supabase. Pulls your entire Strava history, stores it in a hosted database, and renders interactive charts across 9 analysis tabs — deployed as a live web app.

**Live demo:** [strava-insights.streamlit.app](https://strava-insights.streamlit.app) *(password protected)*

---

---

## Features

### 🔍 Insights
Auto-generated analysis of your entire running history — pace trends, consistency patterns, race fitness predictions, and personalized recommendations. Includes best race paces, gap analysis, and 3 actionable recommendations.

### 📈 Time Series
Weekly and monthly distance over time with interactive range selectors (3M / 6M / 1Y / All), 8-period rolling average, and a cumulative mileage area chart — all with a drag-to-zoom range slider.

### ⚡ Pace
Pace trend across every run with a 10-run rolling average, pace distribution histogram, and pace breakdown by day of week. Axes display real pace labels (e.g. `7:30 /mi`) instead of raw numbers.

### 📏 Distance
Distance distribution with race-distance markers (5K / 10K / HM / FM), day-of-week box plots, and a bubble chart of every run sized and colored by pace.

### ❤️ Heart Rate
HR over time with rolling average, HR vs pace scatter colored by distance, and HR distribution histogram.

### ⛰️ Elevation
Monthly elevation gain bar chart, elevation vs distance scatter, and elevation distribution — all in feet.

### 📅 Calendar
GitHub-style weekly activity heatmap per year (pick year from dropdown), plus a month-by-month bar chart with run counts labeled on each bar.

### 📊 Year vs Year
Four bar charts comparing each year: total miles, total runs, average pace, longest run. Includes a year × month heatmap across the full history.

### 📋 Run Log
Full searchable/sortable table of every run (date, name, distance, pace, duration, HR, elevation) with a one-click CSV export.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | [Streamlit](https://streamlit.io) |
| **Charts** | [Plotly](https://plotly.com/python/) |
| **Database** | [Supabase](https://supabase.com) (PostgreSQL) |
| **Data source** | [Strava API v3](https://developers.strava.com/) |
| **Hosting** | [Streamlit Community Cloud](https://share.streamlit.io) (free) |
| **Language** | Python 3.13 |

---

## Architecture

```
Strava API
    │
    ▼
strava.py          ← fetches activities via OAuth refresh token
    │
    ▼
db.py              ← upserts into Supabase (deduplicates by run ID)
    │
    ▼
Supabase (PostgreSQL)
    │
    ▼
dashboard.py       ← Streamlit app reads from Supabase, renders charts
    │
    ▼
strava-insights.streamlit.app
```

**Sync flow:** Clicking "🔄 Sync New Runs" in the sidebar fetches only activities newer than the last saved run, upserts them into Supabase, clears the cache, and rerenders the full dashboard — typically a single API call.

---

## Running Locally

**1. Clone the repo**
```bash
git clone https://github.com/sridhar1986/strava-dashboard.git
cd strava-dashboard
```

**2. Create a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Set up secrets**

Create `.streamlit/secrets.toml`:
```toml
APP_PASSWORD         = "your-password"

SUPABASE_URL         = "https://your-project.supabase.co"
SUPABASE_KEY         = "your-anon-key"

STRAVA_CLIENT_ID     = "your-client-id"
STRAVA_CLIENT_SECRET = "your-client-secret"
STRAVA_REFRESH_TOKEN = "your-refresh-token"
```

**4. Set up Supabase**

Run this SQL once in the Supabase SQL Editor:
```sql
CREATE TABLE IF NOT EXISTS runs (
    id                   bigint PRIMARY KEY,
    name                 text,
    start_date           timestamptz,
    distance             float,
    moving_time          int,
    elapsed_time         int,
    total_elevation_gain float,
    elev_high            float,
    elev_low             float,
    sport_type           text,
    workout_type         text,
    average_speed        float,
    max_speed            float,
    average_heartrate    float,
    max_heartrate        float,
    average_cadence      float,
    suffer_score         float,
    kilojoules           float,
    achievement_count    int,
    kudos_count          int,
    gear_id              text,
    map_summary_polyline text
);
```

**5. Load your data**
```bash
# Fetch all your Strava runs and push to Supabase
python strava.py

# Or migrate from an existing CSV
python migrate.py
```

**6. Run the dashboard**
```bash
streamlit run dashboard.py
```

---

## Strava OAuth Setup

1. Go to [strava.com/settings/api](https://www.strava.com/settings/api) and create an app
2. Run `python reauth.py` — it opens a browser, you authorize, and it writes the refresh token to `strava.py` automatically
3. Copy the refresh token into your `secrets.toml`

---

## Deployment

Deployed for free on [Streamlit Community Cloud](https://share.streamlit.io):

1. Push to a GitHub repo (public or private)
2. Connect at share.streamlit.io → select repo → set main file to `dashboard.py`
3. Add secrets in Advanced Settings
4. Deploy — live in ~2 minutes

---

## Adding Screenshots

Take screenshots of the live app and save them to a `screenshots/` folder:

```
screenshots/
  dashboard.png     ← full dashboard with KPI metrics
  insights.png      ← insights tab
  time_series.png   ← time series tab
  calendar.png      ← calendar heatmap
```

---

## What I Learned / Built

- End-to-end OAuth flow with the Strava API (token refresh, rate limit handling)
- Incremental data sync — only fetches new activities, not the full history each time
- Supabase as a lightweight free PostgreSQL backend for a personal project
- Streamlit for rapid data app development with interactive Plotly charts
- Deploying a Python data app to the cloud with secret management
