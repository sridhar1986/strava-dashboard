"""
Strava Run Dashboard  –  run with:
    streamlit run dashboard.py
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from db import load_runs, save_runs, get_latest_timestamp

KM_TO_MI = 0.621371
M_TO_FT  = 3.28084

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Strava Run Dashboard",
    page_icon="🏃",
    layout="wide",
)

# ── Auth gate ──────────────────────────────────────────────────────────────────
def _check_password() -> bool:
    correct = st.secrets.get("APP_PASSWORD", "")

    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <style>
        .login-box {
            max-width: 380px;
            margin: 8rem auto 0;
            padding: 2.5rem;
            background: #1e1e2e;
            border: 1px solid #333;
            border-radius: 16px;
            text-align: center;
        }
        .login-box h2 { color: #FC4C02; margin-bottom: 0.25rem; }
        .login-box p  { color: #aaa; margin-bottom: 1.5rem; font-size: 0.9rem; }
    </style>
    <div class="login-box">
        <h2>🏃 Strava Dashboard</h2>
        <p>Enter your password to continue</p>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        pwd = st.text_input("Password", type="password", label_visibility="collapsed",
                            placeholder="Enter password…")
        if st.button("Login", use_container_width=True, type="primary"):
            if pwd == correct:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False

if not _check_password():
    st.stop()

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .strava-header {
        background: linear-gradient(135deg, #FC4C02 0%, #e03d00 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .strava-header h1 { margin: 0; font-size: 2rem; }
    .strava-header p  { margin: 0.25rem 0 0; opacity: 0.85; }
    [data-testid="metric-container"] {
        background: #1e1e2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Load & clean ───────────────────────────────────────────────────────────────
def fmt_pace(p):
    if pd.isna(p) or p == 0:
        return "N/A"
    return f"{int(p)}:{int(round((p % 1) * 60)):02d} /mi"


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    df = load_runs()

    if df.empty:
        return df

    df["start_date"] = pd.to_datetime(df["start_date"], utc=True, errors="coerce")
    df["date"]       = df["start_date"].dt.tz_localize(None).dt.normalize()
    df["year"]       = df["start_date"].dt.year.astype(int)
    df["month"]      = df["start_date"].dt.to_period("M")
    df["week"]       = df["start_date"].dt.to_period("W")
    df["day_of_week"]= df["start_date"].dt.day_name()
    df["month_label"]= df["start_date"].dt.strftime("%b %Y")

    df["distance_mi"]     = pd.to_numeric(df["distance"], errors="coerce") / 1000 * KM_TO_MI
    df["moving_time_min"] = pd.to_numeric(df["moving_time"], errors="coerce") / 60
    df["pace_min_per_mi"] = df["moving_time_min"] / df["distance_mi"]
    df["elevation_ft"]    = pd.to_numeric(df["total_elevation_gain"], errors="coerce") * M_TO_FT
    df["avg_hr"]          = pd.to_numeric(df["average_heartrate"], errors="coerce")
    df["max_hr"]          = pd.to_numeric(df["max_heartrate"], errors="coerce")
    df["cadence_spm"]     = pd.to_numeric(df["average_cadence"], errors="coerce") * 2

    df = df[(df["distance_mi"] > 0.3) & df["pace_min_per_mi"].between(3, 20)]

    df["pace_label"]     = df["pace_min_per_mi"].apply(fmt_pace)
    df["duration_label"] = df["moving_time_min"].apply(
        lambda m: f"{int(m//60)}h {int(m%60)}m" if m >= 60 else f"{int(m)}m"
    )
    df["tooltip_name"] = df["name"].fillna("Run")

    return df.sort_values("date").reset_index(drop=True)


try:
    df_all = load_data()
except Exception as e:
    st.error(f"Could not load data from Supabase: **{e}**")
    st.info("Make sure SUPABASE_URL and SUPABASE_KEY are set in `.streamlit/secrets.toml`.")
    st.stop()

if df_all.empty:
    st.error("No valid running data found.")
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/c/cb/Strava_Logo.svg", width=120)
    st.markdown("---")

    # ── Sync button ────────────────────────────────────────────────────────────
    st.subheader("Strava Sync")

    last_date = df_all["date"].max().date() if not df_all.empty else None
    if last_date:
        st.caption(f"Last run: **{last_date}**")

    if st.button("🔄 Sync New Runs", use_container_width=True, type="primary"):
        from strava import get_access_token, get_all_activities

        with st.spinner("Connecting to Strava…"):
            try:
                token    = get_access_token()
                after_ts = get_latest_timestamp()
                new_acts = get_all_activities(token, after_ts=after_ts)
                added    = save_runs(new_acts)

                if added > 0:
                    st.success(f"✅ {added} new run{'s' if added != 1 else ''} synced!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.info("Already up to date.")

            except Exception as e:
                st.error(f"Sync failed: {e}")

    st.markdown("---")
    st.header("Filters")

    years_available = sorted(df_all["year"].unique(), reverse=True)
    selected_years  = st.multiselect("Year(s)", years_available, default=years_available)

    date_min = df_all["date"].min().date()
    date_max = df_all["date"].max().date()
    date_range = st.date_input("Date range", value=(date_min, date_max),
                               min_value=date_min, max_value=date_max)

    min_dist, max_dist = float(df_all["distance_mi"].min()), float(df_all["distance_mi"].max())
    dist_range = st.slider("Distance (mi)", min_dist, max_dist,
                           (min_dist, max_dist), step=0.5)

    st.markdown("---")
    st.caption(f"Total in CSV: **{len(df_all)} runs**")

# ── Apply filters ──────────────────────────────────────────────────────────────
if len(date_range) == 2:
    d_start, d_end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    d_start, d_end = df_all["date"].min(), df_all["date"].max()

df = df_all[
    df_all["year"].isin(selected_years) &
    df_all["date"].between(d_start, d_end) &
    df_all["distance_mi"].between(dist_range[0], dist_range[1])
].copy()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="strava-header">
  <h1>🏃 Strava Run Dashboard</h1>
  <p>{df["date"].min().date()} → {df["date"].max().date()} &nbsp;·&nbsp; {len(df)} runs selected</p>
</div>
""", unsafe_allow_html=True)

# ── KPI metrics ────────────────────────────────────────────────────────────────
total_mi   = df["distance_mi"].sum()
total_h    = int(df["moving_time_min"].sum() // 60)
total_m    = int(df["moving_time_min"].sum() % 60)
total_elev = df["elevation_ft"].sum()
avg_pace   = df["pace_min_per_mi"].mean()
longest    = df["distance_mi"].max()
avg_hr     = df["avg_hr"].mean()
span_days  = max((df["date"].max() - df["date"].min()).days, 1)
mi_per_wk  = total_mi / (span_days / 7)

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("Total Runs",      f"{len(df)}")
k2.metric("Total Distance",  f"{total_mi:,.1f} mi")
k3.metric("Total Time",      f"{total_h}h {total_m}m")
k4.metric("Total Elevation", f"{total_elev:,.0f} ft")
k5.metric("Avg Pace",        fmt_pace(avg_pace))
k6.metric("Longest Run",     f"{longest:.1f} mi")
k7.metric("Avg HR",          f"{avg_hr:.0f} bpm" if not np.isnan(avg_hr) else "N/A")

st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_insights, tab_ts, tab_pace, tab_dist, tab_hr, tab_elev, tab_cal, tab_yoy, tab_log = st.tabs([
    "🔍 Insights", "📈 Time Series", "⚡ Pace", "📏 Distance", "❤️ Heart Rate",
    "⛰️ Elevation", "📅 Calendar", "📊 Year vs Year", "📋 Run Log"
])

ORANGE = "#FC4C02"
BLUE   = "#2D86C5"
GREEN  = "#27AE60"

# ════════════════════════════════════════════════════════════════════════════════
# TAB 0 – INSIGHTS
# ════════════════════════════════════════════════════════════════════════════════
with tab_insights:

    # ── Pre-compute everything needed ──────────────────────────────────────────
    df["hour"] = df["start_date"].dt.hour

    # Yearly stats
    yearly_ins = df.groupby("year").agg(
        runs=("id","count"),
        miles=("distance_mi","sum"),
        avg_pace=("pace_min_per_mi","mean"),
        avg_dist=("distance_mi","mean"),
        longest=("distance_mi","max"),
    ).reset_index()

    # Gap analysis
    df_dates  = df["date"].drop_duplicates().sort_values()
    gaps      = df_dates.diff().dt.days.dropna()
    avg_gap   = gaps.mean()
    max_gap   = gaps.max()
    gap30     = (gaps > 30).sum()
    gap60     = (gaps > 60).sum()

    # Recent vs prior 6 months
    latest = df["date"].max()
    r6 = df[df["date"] >= latest - pd.Timedelta(days=180)]
    p6 = df[(df["date"] >= latest - pd.Timedelta(days=360)) &
             (df["date"] < latest - pd.Timedelta(days=180))]

    pace_delta   = p6["pace_min_per_mi"].mean() - r6["pace_min_per_mi"].mean()
    volume_delta = r6["distance_mi"].sum() - p6["distance_mi"].sum()

    # Best year
    best_year_row = yearly_ins.loc[yearly_ins["miles"].idxmax()]

    # Fastest year (min avg pace, at least 10 runs)
    fast_cand = yearly_ins[yearly_ins["runs"] >= 10]
    fastest_year_row = fast_cand.loc[fast_cand["avg_pace"].idxmin()]

    # Day-of-week stats
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    dow_ins = df.groupby("day_of_week").agg(
        runs=("id","count"),
        avg_dist=("distance_mi","mean"),
        avg_pace=("pace_min_per_mi","mean"),
    ).reindex(day_order)
    best_pace_day  = dow_ins["avg_pace"].idxmin()
    longest_day    = dow_ins["avg_dist"].idxmax()
    most_active_day= dow_ins["runs"].idxmax()

    # Time-of-day
    df["time_bucket"] = pd.cut(df["hour"],
        bins=[0,6,9,12,17,20,24],
        labels=["Early AM (0–6)","Morning (6–9)","Mid-day (9–12)",
                "Afternoon (12–17)","Evening (17–20)","Night (20–24)"])
    fav_time = df["time_bucket"].value_counts().idxmax()

    # Pace buckets
    df["pace_bucket"] = pd.cut(df["pace_min_per_mi"],
        bins=[0,7,8,9,10,20],
        labels=["Sub-7 (fast)","7–8","8–9","9–10","10+ (easy)"])

    # Distance buckets
    df["dist_bucket"] = pd.cut(df["distance_mi"],
        bins=[0,3,5,7,10,13.2,100],
        labels=["<3mi","3–5mi","5–7mi","7–10mi","10–13mi","13mi+"])

    # Pace trend (year over year)
    pace_trend_dir = "improving" if yearly_ins.tail(3)["avg_pace"].is_monotonic_decreasing else "mixed"

    # ── Layout ─────────────────────────────────────────────────────────────────
    st.subheader("Key Findings from Your 13 Years of Running")
    st.caption(f"Based on {len(df)} runs · {df['distance_mi'].sum():,.0f} miles · "
               f"{df['date'].min().date()} → {df['date'].max().date()}")

    # ── Section 1: Performance trajectory ─────────────────────────────────────
    st.markdown("### 🚀 You're Getting Faster")

    c1, c2, c3 = st.columns(3)
    c1.metric("Pace Improvement (6mo)", f"{pace_delta*60:.0f} sec/mi faster",
              delta=f"{pace_delta*60:.0f}s", delta_color="normal")
    c2.metric("Avg Pace — 2023", fmt_pace(yearly_ins[yearly_ins["year"]==2023]["avg_pace"].values[0])
              if 2023 in yearly_ins["year"].values else "N/A")
    c3.metric("Avg Pace — 2025", fmt_pace(yearly_ins[yearly_ins["year"]==2025]["avg_pace"].values[0])
              if 2025 in yearly_ins["year"].values else "N/A")

    # Pace over the years line chart
    fig_pace_yr = px.line(
        yearly_ins[yearly_ins["runs"] >= 5], x="year", y="avg_pace",
        markers=True, color_discrete_sequence=[ORANGE],
        labels={"avg_pace": "Avg Pace (min/mi)", "year": "Year"},
        title="Average Pace by Year (lower = faster)",
    )
    fig_pace_yr.update_yaxes(
        autorange="reversed",
        tickvals=list(range(6, 12)),
        ticktext=[fmt_pace(v) for v in range(6, 12)],
    )
    fig_pace_yr.update_layout(height=300, margin=dict(t=40, b=10))
    st.plotly_chart(fig_pace_yr, use_container_width=True)

    st.info(
        f"**Trend:** Your pace has been consistently improving. "
        f"Fastest full year on record is **{int(fastest_year_row['year'])}** "
        f"at **{fmt_pace(fastest_year_row['avg_pace'])}** avg. "
        f"Your recent 6-month average of **{fmt_pace(r6['pace_min_per_mi'].mean())}** "
        f"is {pace_delta*60:.0f} sec/mi faster than the prior 6 months."
    )

    st.divider()

    # ── Section 2: Consistency ─────────────────────────────────────────────────
    st.markdown("### 📅 Consistency Is Your Biggest Challenge")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Days Between Runs", f"{avg_gap:.0f} days")
    c2.metric("Longest Gap", f"{max_gap:.0f} days (~{max_gap/30:.0f} mo)")
    c3.metric("Gaps > 30 Days", str(gap30))
    c4.metric("Gaps > 60 Days", str(gap60))

    # Volume by year bar
    fig_vol = px.bar(
        yearly_ins, x="year", y="miles", text="runs",
        color="miles", color_continuous_scale="YlOrRd",
        labels={"miles": "Total Miles", "year": "Year", "runs": "# Runs"},
        title="Annual Mileage (with run count labels)",
    )
    fig_vol.update_traces(texttemplate="%{text} runs", textposition="outside")
    fig_vol.update_layout(height=320, margin=dict(t=40, b=10), showlegend=False)
    st.plotly_chart(fig_vol, use_container_width=True)

    # Gap histogram
    fig_gaps = px.histogram(
        gaps.rename("days_between_runs"), x="days_between_runs", nbins=40,
        color_discrete_sequence=[BLUE],
        labels={"days_between_runs": "Days Between Runs"},
        title="Distribution of Gaps Between Runs",
    )
    fig_gaps.add_vline(x=7, line_dash="dash", line_color="green",
                       annotation_text="Weekly", annotation_position="top right")
    fig_gaps.add_vline(x=30, line_dash="dash", line_color="orange",
                       annotation_text="1 month", annotation_position="top right")
    fig_gaps.update_layout(height=280, margin=dict(t=40, b=10))
    st.plotly_chart(fig_gaps, use_container_width=True)

    st.warning(
        f"**{gap30} gaps longer than 30 days** in your history, including a **{max_gap:.0f}-day break** "
        f"(~{max_gap/30:.0f} months). Your peak year was **{int(best_year_row['year'])}** "
        f"with **{best_year_row['miles']:.0f} miles across {best_year_row['runs']:.0f} runs**, "
        f"but volume has been inconsistent since. "
        f"Running more frequently — even short runs — would compound your fitness gains."
    )

    st.divider()

    # ── Section 3: Run type profile ────────────────────────────────────────────
    st.markdown("### 📏 You're a Short–Mid Distance Runner")

    col_l, col_r = st.columns(2)
    with col_l:
        dist_counts = df["dist_bucket"].value_counts().sort_index().reset_index()
        dist_counts.columns = ["Distance", "Runs"]
        fig_db = px.bar(dist_counts, x="Distance", y="Runs",
                        color_discrete_sequence=[ORANGE],
                        title="Run Frequency by Distance")
        fig_db.update_layout(height=300, margin=dict(t=40, b=10))
        st.plotly_chart(fig_db, use_container_width=True)

    with col_r:
        pace_counts = df["pace_bucket"].value_counts().sort_index().reset_index()
        pace_counts.columns = ["Pace Zone", "Runs"]
        fig_pb = px.bar(pace_counts, x="Pace Zone", y="Runs",
                        color_discrete_sequence=[BLUE],
                        title="Run Frequency by Pace Zone")
        fig_pb.update_layout(height=300, margin=dict(t=40, b=10))
        st.plotly_chart(fig_pb, use_container_width=True)

    pct_3_5 = len(df[df["dist_bucket"] == "3–5mi"]) / len(df) * 100
    pct_fast = len(df[df["pace_bucket"].isin(["Sub-7 (fast)", "7–8"])]) / len(df) * 100
    st.info(
        f"**{pct_3_5:.0f}% of your runs are 3–5 miles**, making that your bread-and-butter distance. "
        f"**{pct_fast:.0f}% of runs are at 8:00/mi or faster** — you push the pace consistently. "
        f"You've never logged a full marathon, and only completed a half marathon distance twice. "
        f"Adding occasional long runs (8–12 mi) would help build endurance and race readiness."
    )

    st.divider()

    # ── Section 4: Scheduling patterns ────────────────────────────────────────
    st.markdown("### 🗓️ When You Run Best")

    col_l, col_r = st.columns(2)
    with col_l:
        fig_dow_ins = px.bar(
            dow_ins.reset_index(), x="day_of_week", y="runs",
            color="avg_pace", color_continuous_scale="RdYlGn_r",
            labels={"day_of_week": "Day", "runs": "# Runs", "avg_pace": "Avg Pace"},
            title="Runs by Day of Week (colored by pace)",
            category_orders={"day_of_week": day_order},
        )
        fig_dow_ins.update_coloraxes(
            colorbar=dict(
                tickvals=list(range(7, 10)),
                ticktext=[fmt_pace(v) for v in range(7, 10)],
            )
        )
        fig_dow_ins.update_layout(height=300, margin=dict(t=40, b=10))
        st.plotly_chart(fig_dow_ins, use_container_width=True)

    with col_r:
        tod_data = df["time_bucket"].value_counts().reset_index()
        tod_data.columns = ["Time of Day", "Runs"]
        fig_tod = px.pie(tod_data, names="Time of Day", values="Runs",
                         color_discrete_sequence=px.colors.sequential.Oranges_r,
                         title="Runs by Time of Day")
        fig_tod.update_layout(height=300, margin=dict(t=40, b=10))
        st.plotly_chart(fig_tod, use_container_width=True)

    st.info(
        f"**Tuesday is your most active day** ({dow_ins.loc['Tuesday','runs']:.0f} runs). "
        f"**Thursday gives you your fastest pace** ({fmt_pace(dow_ins.loc['Thursday','avg_pace'])} avg). "
        f"**Sunday and Monday are your longest run days** (~{dow_ins.loc['Sunday','avg_dist']:.1f} mi avg). "
        f"Your most common start time is **{fav_time}** — note that Strava stores times in UTC, "
        f"so your local time may differ."
    )

    st.divider()

    # ── Section 5: Personal Bests ──────────────────────────────────────────────
    st.markdown("### 🏆 Personal Bests & Race Fitness")

    pr_data = []
    for label, lo, hi, full_dist in [
        ("5K",  3.05, 3.25, 3.107),
        ("10K", 6.10, 6.50, 6.214),
        ("HM", 13.00, 13.35, 13.109),
    ]:
        sub = df[df["distance_mi"].between(lo, hi)]
        if not sub.empty:
            row = sub.loc[sub["pace_min_per_mi"].idxmin()]
            finish_min = row["pace_min_per_mi"] * full_dist
            pr_data.append({
                "Race": label,
                "Best Pace": fmt_pace(row["pace_min_per_mi"]),
                "Est. Finish": f"{int(finish_min//60)}:{int(finish_min%60):02d}",
                "Date": str(row["date"].date()),
                "Distance Run": f"{row['distance_mi']:.2f} mi",
            })

    if pr_data:
        st.dataframe(pd.DataFrame(pr_data), use_container_width=True, hide_index=True)

    # Race fitness improvement over time (5K equivalent pace)
    df_sorted_ins = df.sort_values("date").copy()
    df_sorted_ins["rolling_best_pace"] = df_sorted_ins["pace_min_per_mi"].rolling(20, min_periods=5).min()

    fig_pr = go.Figure()
    fig_pr.add_trace(go.Scatter(
        x=df_sorted_ins["date"], y=df_sorted_ins["pace_min_per_mi"],
        mode="markers", marker=dict(color=ORANGE, size=4, opacity=0.3),
        name="Each run",
    ))
    fig_pr.add_trace(go.Scatter(
        x=df_sorted_ins["date"], y=df_sorted_ins["rolling_best_pace"],
        mode="lines", line=dict(color=BLUE, width=2.5),
        name="Rolling best (20 runs)",
    ))
    fig_pr.update_yaxes(
        autorange="reversed",
        tickvals=list(range(6, 12)),
        ticktext=[fmt_pace(v) for v in range(6, 12)],
        title="Pace (min/mi)",
    )
    fig_pr.update_layout(
        title="Pace Ceiling — How Fast You Can Go Over Time",
        height=320, margin=dict(t=40, b=10),
        xaxis=dict(rangeslider=dict(visible=True)),
        legend=dict(orientation="h", y=1.08),
    )
    st.plotly_chart(fig_pr, use_container_width=True)

    best5k_pace = df[df["distance_mi"].between(3.05,3.25)]["pace_min_per_mi"].min() if not df[df["distance_mi"].between(3.05,3.25)].empty else None
    if best5k_pace:
        est_5k = best5k_pace * 3.107
        est_10k = best5k_pace * 1.06 * 6.214
        est_hm  = best5k_pace * 1.15 * 13.109
        st.success(
            f"**Based on your best 5K pace of {fmt_pace(best5k_pace)}, "
            f"your race predictions are:**\n\n"
            f"- 🏃 **5K:** ~{int(est_5k//60)}:{int(est_5k%60):02d}  \n"
            f"- 🏃 **10K:** ~{int(est_10k//60)}:{int(est_10k%60):02d}  \n"
            f"- 🏃 **Half Marathon:** ~{int(est_hm//60)}:{int(est_hm%60):02d}  \n"
            f"- 🏃 **Full Marathon:** ~{int((best5k_pace*1.25*26.219)//60)}:{int((best5k_pace*1.25*26.219)%60):02d} (projected)"
        )

    st.divider()

    # ── Section 6: Summary recommendations ────────────────────────────────────
    st.markdown("### 💡 Recommendations")

    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown("""
**Run More Consistently**
You have 30+ breaks longer than a month. Even 2–3 easy miles during busy weeks would dramatically improve your aerobic base and prevent fitness regression between peaks.
""")
    with r2:
        st.markdown("""
**Add One Long Run Per Week**
92% of your runs are under 7 miles. A weekly long run of 8–12 miles would build the endurance needed to race a half or full marathon at your current fitness level.
""")
    with r3:
        st.markdown("""
**You're Race-Ready for a Sub-20 5K**
Your best 5K pace projects to ~19:20. Structured 5K training (intervals + tempo runs) over 8 weeks could push you comfortably under 19 minutes.
""")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 – TIME SERIES
# ════════════════════════════════════════════════════════════════════════════════
with tab_ts:
    st.subheader("Distance Over Time")

    gran = st.radio("Granularity", ["Weekly", "Monthly"], horizontal=True, key="ts_gran")

    if gran == "Weekly":
        agg = df.groupby("week").agg(
            distance_mi=("distance_mi", "sum"),
            run_count=("id", "count"),
        ).reset_index()
        agg["period_start"] = agg["week"].apply(lambda w: w.start_time)
        x_col = "period_start"
        x_label = "Week"
    else:
        agg = df.groupby("month").agg(
            distance_mi=("distance_mi", "sum"),
            run_count=("id", "count"),
        ).reset_index()
        agg["period_start"] = agg["month"].apply(lambda m: m.start_time)
        x_col = "period_start"
        x_label = "Month"

    agg["rolling_avg"] = agg["distance_mi"].rolling(8, min_periods=2).mean()

    fig_ts = make_subplots(specs=[[{"secondary_y": True}]])
    fig_ts.add_trace(go.Bar(
        x=agg[x_col], y=agg["distance_mi"],
        name="Distance (mi)", marker_color=ORANGE, opacity=0.8,
    ), secondary_y=False)
    fig_ts.add_trace(go.Scatter(
        x=agg[x_col], y=agg["rolling_avg"],
        name="8-period avg", line=dict(color=BLUE, width=2.5),
        mode="lines",
    ), secondary_y=False)
    fig_ts.add_trace(go.Scatter(
        x=agg[x_col], y=agg["run_count"],
        name="# Runs", line=dict(color=GREEN, width=1.5, dash="dot"),
        mode="lines+markers", marker_size=4,
    ), secondary_y=True)

    fig_ts.update_layout(
        height=420, hovermode="x unified",
        xaxis=dict(
            rangeselector=dict(buttons=[
                dict(count=3,  label="3M",  step="month", stepmode="backward"),
                dict(count=6,  label="6M",  step="month", stepmode="backward"),
                dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                dict(count=2,  label="2Y",  step="year",  stepmode="backward"),
                dict(step="all", label="All"),
            ]),
            rangeslider=dict(visible=True),
            type="date",
        ),
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=10),
    )
    fig_ts.update_yaxes(title_text="Distance (mi)", secondary_y=False)
    fig_ts.update_yaxes(title_text="# Runs", secondary_y=True, showgrid=False)
    st.plotly_chart(fig_ts, use_container_width=True)

    # Cumulative distance
    st.subheader("Cumulative Distance")
    df_sorted = df.sort_values("date").copy()
    df_sorted["cum_mi"] = df_sorted["distance_mi"].cumsum()

    fig_cum = px.area(df_sorted, x="date", y="cum_mi",
                      labels={"cum_mi": "Cumulative Miles", "date": "Date"},
                      color_discrete_sequence=[ORANGE])
    fig_cum.update_layout(height=320, margin=dict(t=10, b=10),
                          xaxis=dict(rangeslider=dict(visible=True)))
    st.plotly_chart(fig_cum, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 – PACE
# ════════════════════════════════════════════════════════════════════════════════
with tab_pace:
    st.subheader("Pace Over Time")

    df_p = df.sort_values("date").copy()
    df_p["rolling_pace"] = df_p["pace_min_per_mi"].rolling(10, min_periods=3).mean()
    df_p["pace_label"]   = df_p["pace_min_per_mi"].apply(fmt_pace)

    fig_pace = go.Figure()
    fig_pace.add_trace(go.Scatter(
        x=df_p["date"], y=df_p["pace_min_per_mi"],
        mode="markers",
        marker=dict(color=ORANGE, size=6, opacity=0.5),
        name="Each run",
        customdata=df_p[["tooltip_name", "distance_mi", "pace_label"]],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:.2f} mi · %{customdata[2]}<extra></extra>",
    ))
    fig_pace.add_trace(go.Scatter(
        x=df_p["date"], y=df_p["rolling_pace"],
        mode="lines", line=dict(color=BLUE, width=2.5),
        name="10-run avg",
    ))

    fig_pace.update_yaxes(
        autorange="reversed",
        tickvals=list(range(4, 20)),
        ticktext=[fmt_pace(v) for v in range(4, 20)],
        title="Pace (min/mi)",
    )
    fig_pace.update_layout(
        height=420, hovermode="x unified",
        xaxis=dict(rangeslider=dict(visible=True), type="date"),
        legend=dict(orientation="h", y=1.08),
        margin=dict(t=40, b=10),
    )
    st.plotly_chart(fig_pace, use_container_width=True)

    # Pace distribution
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Pace Distribution")
        fig_pd = px.histogram(df, x="pace_min_per_mi", nbins=30,
                              color_discrete_sequence=[ORANGE],
                              labels={"pace_min_per_mi": "Pace (min/mi)"})
        fig_pd.update_xaxes(
            tickvals=list(range(4, 20)),
            ticktext=[fmt_pace(v) for v in range(4, 20)],
        )
        fig_pd.update_layout(height=320, margin=dict(t=10, b=10))
        st.plotly_chart(fig_pd, use_container_width=True)

    with col_r:
        st.subheader("Pace by Day of Week")
        day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        fig_dow = px.box(df[df["day_of_week"].isin(day_order)],
                         x="day_of_week", y="pace_min_per_mi",
                         category_orders={"day_of_week": day_order},
                         color_discrete_sequence=[ORANGE],
                         labels={"pace_min_per_mi": "Pace (min/mi)", "day_of_week": ""})
        fig_dow.update_yaxes(
            autorange="reversed",
            tickvals=list(range(5, 18)),
            ticktext=[fmt_pace(v) for v in range(5, 18)],
        )
        fig_dow.update_layout(height=320, margin=dict(t=10, b=10))
        st.plotly_chart(fig_dow, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 – DISTANCE
# ════════════════════════════════════════════════════════════════════════════════
with tab_dist:
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Distance Distribution")
        fig_dh = px.histogram(df, x="distance_mi", nbins=35,
                              color_discrete_sequence=[ORANGE],
                              labels={"distance_mi": "Distance (mi)"})
        for v, lbl in [(3.1, "5K"), (6.2, "10K"), (13.1, "HM"), (26.2, "FM")]:
            if df["distance_mi"].max() > v - 0.3:
                fig_dh.add_vline(x=v, line_dash="dash", line_color="white", opacity=0.6,
                                 annotation_text=lbl, annotation_position="top right")
        fig_dh.update_layout(height=360, margin=dict(t=10, b=10))
        st.plotly_chart(fig_dh, use_container_width=True)

    with col_r:
        st.subheader("Distance by Day of Week")
        day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        fig_dw = px.box(df[df["day_of_week"].isin(day_order)],
                        x="day_of_week", y="distance_mi",
                        category_orders={"day_of_week": day_order},
                        color_discrete_sequence=[ORANGE],
                        labels={"distance_mi": "Distance (mi)", "day_of_week": ""})
        fig_dw.update_layout(height=360, margin=dict(t=10, b=10))
        st.plotly_chart(fig_dw, use_container_width=True)

    st.subheader("Every Run — Distance & Pace")
    fig_scatter = px.scatter(
        df, x="date", y="distance_mi",
        color="pace_min_per_mi", size="distance_mi",
        color_continuous_scale="RdYlGn_r",
        hover_data={"tooltip_name": True, "pace_label": True,
                    "distance_mi": ":.2f", "date": True,
                    "pace_min_per_mi": False},
        labels={"distance_mi": "Distance (mi)", "date": "Date",
                "pace_min_per_mi": "Pace", "tooltip_name": "Name",
                "pace_label": "Pace"},
    )
    fig_scatter.update_coloraxes(
        colorbar=dict(
            title="Pace",
            tickvals=list(range(6, 16, 2)),
            ticktext=[fmt_pace(v) for v in range(6, 16, 2)],
        )
    )
    fig_scatter.update_layout(height=380, margin=dict(t=10, b=10),
                               xaxis=dict(rangeslider=dict(visible=True)))
    st.plotly_chart(fig_scatter, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 – HEART RATE
# ════════════════════════════════════════════════════════════════════════════════
with tab_hr:
    hr_df = df[df["avg_hr"].notna()].copy()

    if hr_df.empty:
        st.info("No heart rate data in the selected range.")
    else:
        hr_df = hr_df.sort_values("date")
        hr_df["rolling_hr"] = hr_df["avg_hr"].rolling(10, min_periods=3).mean()

        st.subheader("Heart Rate Over Time")
        fig_hrt = go.Figure()
        fig_hrt.add_trace(go.Scatter(
            x=hr_df["date"], y=hr_df["avg_hr"],
            mode="markers", marker=dict(color=ORANGE, size=5, opacity=0.45),
            name="Each run",
            customdata=hr_df[["tooltip_name", "distance_mi", "pace_label"]],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:.2f} mi · %{customdata[2]}<br>HR: %{y:.0f} bpm<extra></extra>",
        ))
        fig_hrt.add_trace(go.Scatter(
            x=hr_df["date"], y=hr_df["rolling_hr"],
            mode="lines", line=dict(color=BLUE, width=2.5),
            name="10-run avg",
        ))
        fig_hrt.update_layout(
            height=380, hovermode="x unified",
            yaxis_title="Avg HR (bpm)",
            xaxis=dict(rangeslider=dict(visible=True), type="date"),
            legend=dict(orientation="h", y=1.08),
            margin=dict(t=40, b=10),
        )
        st.plotly_chart(fig_hrt, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("HR vs Pace")
            fig_hrp = px.scatter(
                hr_df, x="avg_hr", y="pace_min_per_mi",
                color="distance_mi", size="distance_mi",
                color_continuous_scale="YlOrRd",
                hover_data={"tooltip_name": True, "pace_label": True,
                            "avg_hr": True, "distance_mi": ":.2f",
                            "pace_min_per_mi": False},
                labels={"avg_hr": "Avg HR (bpm)", "pace_min_per_mi": "Pace",
                        "distance_mi": "Distance (mi)", "tooltip_name": "Name",
                        "pace_label": "Pace"},
            )
            fig_hrp.update_yaxes(
                autorange="reversed",
                tickvals=list(range(5, 18)),
                ticktext=[fmt_pace(v) for v in range(5, 18)],
            )
            fig_hrp.update_layout(height=360, margin=dict(t=10, b=10))
            st.plotly_chart(fig_hrp, use_container_width=True)

        with col_r:
            st.subheader("HR Distribution")
            fig_hrd = px.histogram(hr_df, x="avg_hr", nbins=25,
                                   color_discrete_sequence=["#e74c3c"],
                                   labels={"avg_hr": "Avg HR (bpm)"})
            fig_hrd.update_layout(height=360, margin=dict(t=10, b=10))
            st.plotly_chart(fig_hrd, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 – ELEVATION
# ════════════════════════════════════════════════════════════════════════════════
with tab_elev:
    elev_df = df[df["elevation_ft"].notna() & (df["elevation_ft"] > 0)].copy()

    if elev_df.empty:
        st.info("No elevation data in the selected range.")
    else:
        st.subheader("Elevation Gain Over Time")
        monthly_elev = elev_df.groupby("month").agg(
            elevation_ft=("elevation_ft", "sum"),
        ).reset_index()
        monthly_elev["period_start"] = monthly_elev["month"].apply(lambda m: m.start_time)

        fig_elev_ts = px.bar(monthly_elev, x="period_start", y="elevation_ft",
                             color_discrete_sequence=[GREEN],
                             labels={"elevation_ft": "Elevation (ft)", "period_start": "Month"})
        fig_elev_ts.update_layout(height=350, margin=dict(t=10, b=10),
                                   xaxis=dict(rangeslider=dict(visible=True)))
        st.plotly_chart(fig_elev_ts, use_container_width=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("Elevation vs Distance")
            fig_evd = px.scatter(
                elev_df, x="distance_mi", y="elevation_ft",
                color="pace_min_per_mi", color_continuous_scale="RdYlGn_r",
                hover_data={"tooltip_name": True, "pace_label": True,
                            "distance_mi": ":.2f", "elevation_ft": ":.0f",
                            "pace_min_per_mi": False},
                labels={"distance_mi": "Distance (mi)",
                        "elevation_ft": "Elevation Gain (ft)",
                        "tooltip_name": "Name", "pace_label": "Pace"},
            )
            fig_evd.update_layout(height=360, margin=dict(t=10, b=10))
            st.plotly_chart(fig_evd, use_container_width=True)

        with col_r:
            st.subheader("Elevation Distribution")
            fig_evh = px.histogram(elev_df, x="elevation_ft", nbins=30,
                                   color_discrete_sequence=[GREEN],
                                   labels={"elevation_ft": "Elevation Gain (ft)"})
            fig_evh.update_layout(height=360, margin=dict(t=10, b=10))
            st.plotly_chart(fig_evh, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 6 – CALENDAR HEATMAP
# ════════════════════════════════════════════════════════════════════════════════
with tab_cal:
    st.subheader("Activity Calendar — Weekly Mileage Heatmap")

    cal_df = df.copy()
    cal_df["week_start"] = cal_df["date"] - pd.to_timedelta(cal_df["date"].dt.weekday, unit="D")
    cal_df["dow"]        = cal_df["date"].dt.weekday  # 0=Mon

    weekly_cal = cal_df.groupby(["week_start", "dow"]).agg(
        distance_mi=("distance_mi", "sum"),
        run_count=("id", "count"),
    ).reset_index()

    year_sel = st.selectbox("Year", sorted(df["year"].unique(), reverse=True), key="cal_year")
    cal_year = weekly_cal[weekly_cal["week_start"].dt.year == year_sel].copy()

    if cal_year.empty:
        st.info(f"No runs in {year_sel}.")
    else:
        pivot = cal_year.pivot(index="dow", columns="week_start", values="distance_mi").fillna(0)

        dow_labels = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        week_labels = [str(c.date()) for c in pivot.columns]

        fig_cal = go.Figure(go.Heatmap(
            z=pivot.values,
            x=week_labels,
            y=dow_labels,
            colorscale="YlOrRd",
            colorbar=dict(title="mi"),
            hovertemplate="Week: %{x}<br>%{y}: %{z:.1f} mi<extra></extra>",
        ))
        fig_cal.update_layout(
            height=280,
            yaxis=dict(autorange="reversed"),
            margin=dict(t=10, b=10),
            xaxis=dict(tickangle=45, tickfont=dict(size=9)),
        )
        st.plotly_chart(fig_cal, use_container_width=True)

        # Monthly summary for the selected year
        st.subheader(f"{year_sel} — Month by Month")
        year_df = df[df["year"] == year_sel].copy()
        monthly_yr = year_df.groupby(year_df["date"].dt.strftime("%b")).agg(
            distance_mi=("distance_mi", "sum"),
            run_count=("id", "count"),
            avg_pace=("pace_min_per_mi", "mean"),
        ).reindex(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]).dropna()
        monthly_yr["avg_pace_label"] = monthly_yr["avg_pace"].apply(fmt_pace)

        fig_myr = px.bar(monthly_yr, x=monthly_yr.index, y="distance_mi",
                         text="run_count",
                         color_discrete_sequence=[ORANGE],
                         labels={"distance_mi": "Distance (mi)", "x": "Month"})
        fig_myr.update_traces(texttemplate="%{text} runs", textposition="outside")
        fig_myr.update_layout(height=320, margin=dict(t=10, b=10))
        st.plotly_chart(fig_myr, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 – YEAR-OVER-YEAR
# ════════════════════════════════════════════════════════════════════════════════
with tab_yoy:
    yearly = df.groupby("year").agg(
        total_mi=("distance_mi", "sum"),
        total_runs=("id", "count"),
        avg_pace=("pace_min_per_mi", "mean"),
        avg_distance=("distance_mi", "mean"),
        longest_run=("distance_mi", "max"),
        total_elev=("elevation_ft", "sum"),
    ).reset_index()
    yearly["avg_pace_label"] = yearly["avg_pace"].apply(fmt_pace)
    yearly["year"] = yearly["year"].astype(str)

    st.subheader("Year-over-Year Overview")
    col1, col2 = st.columns(2)

    with col1:
        fig_y1 = px.bar(yearly, x="year", y="total_mi", text="total_mi",
                        color_discrete_sequence=[ORANGE],
                        labels={"total_mi": "Total Miles", "year": "Year"})
        fig_y1.update_traces(texttemplate="%{text:.0f} mi", textposition="outside")
        fig_y1.update_layout(title="Total Distance", height=320, margin=dict(t=40, b=10))
        st.plotly_chart(fig_y1, use_container_width=True)

    with col2:
        fig_y2 = px.bar(yearly, x="year", y="total_runs", text="total_runs",
                        color_discrete_sequence=[BLUE],
                        labels={"total_runs": "# Runs", "year": "Year"})
        fig_y2.update_traces(texttemplate="%{text}", textposition="outside")
        fig_y2.update_layout(title="Total Runs", height=320, margin=dict(t=40, b=10))
        st.plotly_chart(fig_y2, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig_y3 = px.bar(yearly, x="year", y="avg_pace", text="avg_pace_label",
                        color_discrete_sequence=[GREEN],
                        labels={"avg_pace": "Avg Pace (min/mi)", "year": "Year"})
        fig_y3.update_yaxes(
            autorange="reversed",
            tickvals=list(range(6, 16)),
            ticktext=[fmt_pace(v) for v in range(6, 16)],
        )
        fig_y3.update_traces(textposition="outside")
        fig_y3.update_layout(title="Avg Pace (lower = faster)", height=320, margin=dict(t=40, b=10))
        st.plotly_chart(fig_y3, use_container_width=True)

    with col4:
        fig_y4 = px.bar(yearly, x="year", y="longest_run", text="longest_run",
                        color_discrete_sequence=["#8E44AD"],
                        labels={"longest_run": "Longest Run (mi)", "year": "Year"})
        fig_y4.update_traces(texttemplate="%{text:.1f} mi", textposition="outside")
        fig_y4.update_layout(title="Longest Run", height=320, margin=dict(t=40, b=10))
        st.plotly_chart(fig_y4, use_container_width=True)

    # Monthly distance heatmap across years
    st.subheader("Monthly Distance Heatmap (All Years)")
    df["month_num"] = df["start_date"].dt.month
    df["month_name"] = df["start_date"].dt.strftime("%b")
    pivot_yoy = df.groupby(["year", "month_num"])["distance_mi"].sum().reset_index()
    pivot_yoy = pivot_yoy.pivot(index="year", columns="month_num", values="distance_mi").fillna(0)
    pivot_yoy.columns = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][:len(pivot_yoy.columns)]

    fig_yoy_hm = px.imshow(
        pivot_yoy,
        color_continuous_scale="YlOrRd",
        labels=dict(color="Miles"),
        aspect="auto",
    )
    fig_yoy_hm.update_layout(height=max(250, len(pivot_yoy) * 35), margin=dict(t=10, b=10))
    st.plotly_chart(fig_yoy_hm, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 8 – RUN LOG
# ════════════════════════════════════════════════════════════════════════════════
with tab_log:
    st.subheader("Run Log")

    log = df[["date", "tooltip_name", "distance_mi", "pace_label",
              "duration_label", "avg_hr", "elevation_ft", "day_of_week"]].copy()
    log = log.rename(columns={
        "date": "Date", "tooltip_name": "Name",
        "distance_mi": "Distance (mi)", "pace_label": "Pace",
        "duration_label": "Duration", "avg_hr": "Avg HR",
        "elevation_ft": "Elev (ft)", "day_of_week": "Day",
    })
    log["Distance (mi)"] = log["Distance (mi)"].round(2)
    log["Avg HR"]        = log["Avg HR"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    log["Elev (ft)"]     = log["Elev (ft)"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")
    log["Date"]          = log["Date"].dt.strftime("%Y-%m-%d")
    log = log.sort_values("Date", ascending=False).reset_index(drop=True)

    st.dataframe(log, use_container_width=True, height=500)

    csv_export = log.to_csv(index=False).encode()
    st.download_button("⬇️ Download CSV", csv_export, "my_runs.csv", "text/csv")
