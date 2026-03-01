"""
agent.py — LLM-powered running coach.

Provides three functions:
  analyze_run(run, df_history)          → markdown insight for a single run
  weekly_summary(df)                    → markdown weekly training summary
  chat(question, df, history)           → answer a natural-language question
"""

import os
import json
import pandas as pd

# ── Helpers ────────────────────────────────────────────────────────────────────

def _api_key() -> str:
    # dashboard.py injects the key into os.environ after reading st.secrets
    return os.environ.get("OPENAI_API_KEY", "")


def _client():
    key = _api_key()
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)


def _fmt_pace(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "N/A"
    if pd.isna(p) or p <= 0:
        return "N/A"
    return f"{int(p)}:{int(round((p % 1) * 60)):02d}"


def _run_dict(row: pd.Series) -> dict:
    return {
        "date":         str(row.get("date", ""))[:10],
        "name":         row.get("tooltip_name", "Run"),
        "distance_mi":  round(float(row.get("distance_mi") or 0), 2),
        "pace":         _fmt_pace(row.get("pace_min_per_mi")),
        "duration_min": round(float(row.get("moving_time_min") or 0), 1),
        "elevation_ft": round(float(row["elevation_ft"]), 0) if pd.notna(row.get("elevation_ft")) else None,
        "avg_hr":       round(float(row["avg_hr"]), 0)       if pd.notna(row.get("avg_hr"))       else None,
    }


def _context(df: pd.DataFrame) -> str:
    """Compact text summary of the athlete's full history for the LLM system prompt."""
    if df.empty:
        return "No running history available."

    now  = df["date"].max()
    d30  = df[df["date"] >= now - pd.Timedelta(days=30)]
    d90  = df[df["date"] >= now - pd.Timedelta(days=90)]
    hr   = df["avg_hr"].dropna()
    hr30 = d30["avg_hr"].dropna()

    def _sum(subset):
        return f"{subset['distance_mi'].sum():.1f} mi across {len(subset)} runs"

    lines = [
        "=== Athlete Running History ===",
        f"Span : {df['date'].min().date()} → {now.date()}  |  Total runs: {len(df)}",
        f"Total distance: {df['distance_mi'].sum():.1f} mi",
        "",
        "All-time bests:",
        f"  Fastest pace : {_fmt_pace(df['pace_min_per_mi'].min())} /mi",
        f"  Longest run  : {df['distance_mi'].max():.2f} mi",
        (f"  Most elev    : {df['elevation_ft'].max():.0f} ft"
         if df["elevation_ft"].notna().any() else ""),
        "",
        "All-time averages:",
        f"  Avg distance : {df['distance_mi'].mean():.2f} mi",
        f"  Avg pace     : {_fmt_pace(df['pace_min_per_mi'].mean())} /mi",
        (f"  Avg HR       : {hr.mean():.0f} bpm" if not hr.empty else ""),
        "",
        f"Last 30 days : {_sum(d30)}" + (f"  |  avg pace {_fmt_pace(d30['pace_min_per_mi'].mean())} /mi" if not d30.empty else ""),
        (f"              avg HR {hr30.mean():.0f} bpm" if not hr30.empty else ""),
        f"Last 90 days : {_sum(d90)}",
        "",
        "Last 10 runs (oldest → newest):",
    ]
    for _, row in df.tail(10).iterrows():
        hr_str = f"  HR={row['avg_hr']:.0f}" if pd.notna(row.get("avg_hr")) else ""
        lines.append(
            f"  {str(row['date'])[:10]}  {row['distance_mi']:.2f} mi"
            f" @ {_fmt_pace(row['pace_min_per_mi'])} /mi{hr_str}"
        )

    return "\n".join(l for l in lines if l is not None)


def _call(client, system: str, messages: list, max_tokens: int = 600) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}] + messages,
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


_NO_KEY_MSG = (
    "_**AI Coach disabled.** Add `OPENAI_API_KEY` to `.streamlit/secrets.toml` "
    "(and Streamlit Cloud secrets) to enable AI insights._"
)


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_run(run: pd.Series, df_history: pd.DataFrame) -> str:
    """Analyze the most recent run vs. history. Returns markdown."""
    c = _client()
    if not c:
        return _NO_KEY_MSG

    system = (
        "You are an expert running coach AI. Analyze this athlete's latest run against their history. "
        "Be specific with numbers, encouraging but honest. "
        "Produce 3–5 markdown bullet points covering:\n"
        "1. How this run compares to recent averages (pace, distance, HR)\n"
        "2. Any notable achievements or concerns\n"
        "3. One concrete, actionable training tip for the next run.\n"
        "Keep it punchy — no fluff."
    )
    user = (
        f"**Latest run:**\n```json\n{json.dumps(_run_dict(run), indent=2)}\n```\n\n"
        f"{_context(df_history)}"
    )
    return _call(c, system, [{"role": "user", "content": user}])


def weekly_summary(df: pd.DataFrame) -> str:
    """Generate a weekly training summary with forward-looking advice. Returns markdown."""
    c = _client()
    if not c:
        return _NO_KEY_MSG

    now          = df["date"].max()
    last_monday  = now - pd.Timedelta(days=int(now.dayofweek))
    this_week    = df[df["date"] >= last_monday]

    system = (
        "You are an expert running coach. Write a punchy weekly training summary using emojis and markdown. "
        "Be concrete with numbers. Cover:\n"
        "• This week's load vs the prior 4-week average\n"
        "• A trend observation (pace improving? mileage building safely?)\n"
        "• 2 specific, actionable recommendations for next week.\n"
        "Aim for 5–7 bullets. No fluff."
    )
    user = (
        f"**This week** ({last_monday.date()} → {now.date()}): "
        f"{len(this_week)} run(s), {this_week['distance_mi'].sum():.1f} mi.\n\n"
        f"{_context(df)}"
    )
    return _call(c, system, [{"role": "user", "content": user}], max_tokens=700)


def chat(question: str, df: pd.DataFrame, history: list) -> str:
    """
    Answer a natural-language question about the runner's data.
    history: list of {"role": "user"|"assistant", "content": str}
    """
    c = _client()
    if not c:
        return _NO_KEY_MSG

    recent = [_run_dict(row) for _, row in df.tail(20).iterrows()]

    system = (
        f"You are an expert running coach AI with access to this athlete's full history. "
        f"Answer questions with specifics — cite real numbers from their data. "
        f"Be conversational, encouraging, and data-driven.\n\n"
        f"{_context(df)}\n\n"
        f"Detailed last 20 runs (for specific lookups):\n"
        f"```json\n{json.dumps(recent, indent=2)}\n```"
    )
    msgs = list(history) + [{"role": "user", "content": question}]
    return _call(c, system, msgs, max_tokens=800)
