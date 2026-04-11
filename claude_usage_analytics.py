"""Analytics engine for Claude Code token usage.

Pure functions: records in, stats out. No CLI logic.
"""

import sys
import json as _json
import statistics
from collections import defaultdict

# API pricing per 1M tokens (USD)
API_PRICING = {
    "opus": {
        "input": 15.00,
        "output": 75.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "sonnet": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "haiku": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
}

_MODEL_KEYWORDS = ["opus", "sonnet", "haiku"]


def resolve_model_name(model_str: str) -> str:
    """Map a full model string to a pricing key.

    Returns 'opus', 'sonnet', 'haiku', or 'unknown'.
    """
    lower = model_str.lower()
    for kw in _MODEL_KEYWORDS:
        if kw in lower:
            return kw
    return "unknown"


def get_record_cost(rec: dict) -> float:
    """Calculate equivalent API cost for a single record in USD."""
    model_key = resolve_model_name(rec.get("model", ""))
    if model_key == "unknown":
        return 0.0

    pricing = API_PRICING[model_key]
    cost = (
        rec["input_tokens"] * pricing["input"]
        + rec["output_tokens"] * pricing["output"]
        + rec["cache_creation_input_tokens"] * pricing["cache_write"]
        + rec["cache_read_input_tokens"] * pricing["cache_read"]
    ) / 1_000_000
    return cost


def _get_metric_value(rec: dict, metric: str) -> int:
    """Extract token count for the chosen metric."""
    if metric == "output":
        return rec["output_tokens"]
    elif metric == "input":
        return rec["input_tokens"]
    elif metric == "cache":
        return rec["cache_creation_input_tokens"] + rec["cache_read_input_tokens"]
    else:  # total
        return rec["input_tokens"] + rec["output_tokens"]


def compute_burn_rate(records: list, metric: str, days: int) -> dict:
    """Compute burn rate statistics.

    Returns dict with: daily_avg, weekly_avg, weekday_avg, weekend_avg,
    total, trend_pct.
    """
    if not records:
        return {
            "daily_avg": 0, "weekly_avg": 0, "weekday_avg": 0,
            "weekend_avg": 0, "total": 0, "trend_pct": 0.0,
        }

    total = sum(_get_metric_value(r, metric) for r in records)

    # Per-day totals
    day_totals = defaultdict(int)
    for r in records:
        day_totals[r["date"]] += _get_metric_value(r, metric)

    # Weekday vs weekend
    weekday_by_day = defaultdict(int)
    weekend_by_day = defaultdict(int)
    for r in records:
        val = _get_metric_value(r, metric)
        if r["weekday"] < 5:
            weekday_by_day[r["date"]] += val
        else:
            weekend_by_day[r["date"]] += val

    weekday_avg = (
        sum(weekday_by_day.values()) / len(weekday_by_day)
        if weekday_by_day else 0
    )
    weekend_avg = (
        sum(weekend_by_day.values()) / len(weekend_by_day)
        if weekend_by_day else 0
    )

    daily_avg = total / days if days > 0 else 0
    weekly_avg = daily_avg * 7

    # Trend: compare second half vs first half
    sorted_dates = sorted(day_totals.keys())
    mid = len(sorted_dates) // 2
    if mid > 0:
        first_half = sum(day_totals[d] for d in sorted_dates[:mid])
        second_half = sum(day_totals[d] for d in sorted_dates[mid:])
        trend_pct = (
            ((second_half - first_half) / first_half * 100)
            if first_half > 0 else 0.0
        )
    else:
        trend_pct = 0.0

    return {
        "daily_avg": int(daily_avg),
        "weekly_avg": int(weekly_avg),
        "weekday_avg": int(weekday_avg),
        "weekend_avg": int(weekend_avg),
        "total": total,
        "trend_pct": round(trend_pct, 1),
    }


def compute_session_stats(records: list, metric: str, days: int) -> dict:
    """Compute per-session statistics."""
    if not records:
        return {
            "count": 0, "avg": 0, "median": 0,
            "largest_tokens": 0, "largest_project": "",
            "sessions_per_day": 0.0,
        }

    sessions = defaultdict(lambda: {"total": 0, "project": ""})
    for r in records:
        sid = r["session"]
        sessions[sid]["total"] += _get_metric_value(r, metric)
        sessions[sid]["project"] = r["project"]

    totals = [s["total"] for s in sessions.values()]
    count = len(totals)
    largest_sid = max(sessions, key=lambda k: sessions[k]["total"])

    return {
        "count": count,
        "avg": sum(totals) / count,
        "median": int(statistics.median(totals)),
        "largest_tokens": sessions[largest_sid]["total"],
        "largest_project": sessions[largest_sid]["project"],
        "sessions_per_day": round(count / days, 1) if days > 0 else 0.0,
    }


def compute_hourly_breakdown(records: list, metric: str) -> dict:
    """Compute hour-of-day usage breakdown."""
    if not records:
        return {
            "hour_totals": {}, "peak_window_start": 0,
            "peak_window_pct": 0, "peak_hour": 0, "peak_hour_pct": 0,
            "weekday_hours": {}, "weekend_hours": {},
        }

    hour_totals = defaultdict(int)
    weekday_hours = defaultdict(int)
    weekend_hours = defaultdict(int)

    for r in records:
        val = _get_metric_value(r, metric)
        hour_totals[r["hour"]] += val
        if r["weekday"] < 5:
            weekday_hours[r["hour"]] += val
        else:
            weekend_hours[r["hour"]] += val

    total = sum(hour_totals.values())

    best_start = 0
    best_sum = 0
    for start in range(24):
        window_sum = sum(hour_totals.get((start + h) % 24, 0) for h in range(4))
        if window_sum > best_sum:
            best_sum = window_sum
            best_start = start

    peak_hour = max(hour_totals, key=hour_totals.get) if hour_totals else 0

    return {
        "hour_totals": dict(hour_totals),
        "peak_window_start": best_start,
        "peak_window_pct": round(best_sum / total * 100, 1) if total else 0,
        "peak_hour": peak_hour,
        "peak_hour_pct": round(
            hour_totals.get(peak_hour, 0) / total * 100, 1
        ) if total else 0,
        "weekday_hours": dict(weekday_hours),
        "weekend_hours": dict(weekend_hours),
    }


def compute_model_mix(records: list) -> dict:
    """Compute token and cost breakdown by model."""
    if not records:
        return {"models": []}

    by_model = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_write": 0, "cache_read": 0,
    })

    for r in records:
        key = resolve_model_name(r.get("model", ""))
        if key == "unknown":
            continue
        by_model[key]["input"] += r["input_tokens"]
        by_model[key]["output"] += r["output_tokens"]
        by_model[key]["cache_write"] += r["cache_creation_input_tokens"]
        by_model[key]["cache_read"] += r["cache_read_input_tokens"]

    grand_total = sum(
        m["input"] + m["output"] for m in by_model.values()
    )

    models = []
    for name in sorted(by_model, key=lambda k: by_model[k]["input"] + by_model[k]["output"], reverse=True):
        m = by_model[name]
        total_tokens = m["input"] + m["output"]
        pricing = API_PRICING.get(name, API_PRICING["sonnet"])
        est_cost = (
            m["input"] * pricing["input"]
            + m["output"] * pricing["output"]
            + m["cache_write"] * pricing["cache_write"]
            + m["cache_read"] * pricing["cache_read"]
        ) / 1_000_000

        models.append({
            "name": name,
            "input_tokens": m["input"],
            "output_tokens": m["output"],
            "cache_write": m["cache_write"],
            "cache_read": m["cache_read"],
            "total_tokens": total_tokens,
            "pct": round(total_tokens / grand_total * 100, 1) if grand_total else 0,
            "est_cost": round(est_cost, 2),
        })

    return {"models": models}


def compute_project_rankings(records: list, metric: str, top_n: int) -> list:
    """Rank projects by token usage."""
    if not records:
        return []

    projects = defaultdict(lambda: {
        "total": 0, "sessions": set(), "models": defaultdict(int), "cost": 0.0,
    })

    for r in records:
        p = projects[r["project"]]
        p["total"] += _get_metric_value(r, metric)
        p["sessions"].add(r["session"])
        model_key = resolve_model_name(r.get("model", ""))
        p["models"][model_key] += _get_metric_value(r, metric)
        p["cost"] += get_record_cost(r)

    ranked = sorted(projects.items(), key=lambda x: x[1]["total"], reverse=True)

    return [
        {
            "name": name,
            "total_tokens": data["total"],
            "session_count": len(data["sessions"]),
            "primary_model": max(data["models"], key=data["models"].get),
            "est_cost": round(data["cost"], 2),
        }
        for name, data in ranked[:top_n]
    ]


def compute_api_cost(records: list, days: int) -> dict:
    """Compute equivalent API cost breakdown."""
    if not records:
        return {
            "total": 0.0, "per_day_avg": 0.0,
            "by_project": {}, "by_model": {},
        }

    by_project = defaultdict(float)
    by_model = defaultdict(float)
    total = 0.0

    for r in records:
        cost = get_record_cost(r)
        total += cost
        by_project[r["project"]] += cost
        by_model[resolve_model_name(r.get("model", ""))] += cost

    by_model.pop("unknown", None)

    return {
        "total": round(total, 2),
        "per_day_avg": round(total / days, 2) if days > 0 else 0.0,
        "by_project": {k: round(v, 2) for k, v in by_project.items()},
        "by_model": {k: round(v, 2) for k, v in by_model.items()},
    }


def compute_all(records: list, metric: str, days: int, top_n: int) -> dict:
    """Compute all analytics in one call."""
    return {
        "burn_rate": compute_burn_rate(records, metric, days),
        "sessions": compute_session_stats(records, metric, days),
        "hours": compute_hourly_breakdown(records, metric),
        "model_mix": compute_model_mix(records),
        "projects": compute_project_rankings(records, metric, top_n),
        "cost": compute_api_cost(records, days),
    }


def _fmt_tokens(n: int) -> str:
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _fmt_cost(n: float) -> str:
    """Format USD cost."""
    if n >= 1000:
        return f"${n:,.0f}"
    return f"${n:.2f}"


def _fmt_hour(h: int) -> str:
    """Format hour as 12h clock."""
    if h == 0:
        return "12am"
    if h == 12:
        return "12pm"
    return f"{h}am" if h < 12 else f"{h - 12}pm"


def render_terminal_report(stats: dict, metric: str, days: int):
    """Print ANSI-formatted analytics summary to stdout."""
    br = stats["burn_rate"]
    sess = stats["sessions"]
    hrs = stats["hours"]
    mix = stats["model_mix"]
    proj = stats["projects"]
    cost = stats["cost"]

    w = 60

    # Header
    print(f"\n\033[1m╔{'═' * (w - 2)}╗\033[0m")
    title = f"Claude Code Usage Report · Last {days} days"
    print(f"\033[1m║  {title:<{w - 4}}║\033[0m")
    print(f"\033[1m╚{'═' * (w - 2)}╝\033[0m")

    # Burn Rate
    trend_arrow = "▲" if br["trend_pct"] > 0 else "▼" if br["trend_pct"] < 0 else "─"
    trend_sign = "+" if br["trend_pct"] > 0 else ""
    print(f"\n\033[1mBURN RATE\033[0m")
    print(f"  Daily avg:   {_fmt_tokens(br['daily_avg']):>8}    "
          f"Weekday: {_fmt_tokens(br['weekday_avg'])}   "
          f"Weekend: {_fmt_tokens(br['weekend_avg'])}")
    print(f"  Weekly avg:  {_fmt_tokens(br['weekly_avg']):>8}    "
          f"Trend: {trend_arrow} {trend_sign}{br['trend_pct']:.0f}% vs prior period")
    print(f"  Total:       {_fmt_tokens(br['total']):>8}    "
          f"Est. API cost: {_fmt_cost(cost['total'])}")

    # Model Mix
    if mix["models"]:
        print(f"\n\033[1mMODEL MIX\033[0m")
        for m in mix["models"]:
            label = m["name"].capitalize()
            print(f"  {label:<12} {m['pct']:>4.0f}%   "
                  f"{_fmt_tokens(m['total_tokens']):>8} tokens   "
                  f"{_fmt_cost(m['est_cost'])}")

    # Top Projects
    if proj:
        print(f"\n\033[1mTOP PROJECTS\033[0m")
        for i, p in enumerate(proj, 1):
            print(f"  {i}. {p['name']:<22} "
                  f"{_fmt_tokens(p['total_tokens']):>8} tokens   "
                  f"{p['session_count']:>3} sessions   "
                  f"{_fmt_cost(p['est_cost'])}")

    # Sessions
    print(f"\n\033[1mSESSIONS\033[0m")
    print(f"  Total: {sess['count']}    "
          f"Avg: {_fmt_tokens(int(sess['avg']))}/session    "
          f"Largest: {_fmt_tokens(sess['largest_tokens'])} ({sess['largest_project']})")

    # Peak Hours
    if hrs["hour_totals"]:
        print(f"\n\033[1mPEAK HOURS\033[0m")
        max_hour_val = max(hrs["hour_totals"].values()) if hrs["hour_totals"] else 1
        bar = ""
        for h in range(24):
            val = hrs["hour_totals"].get(h, 0)
            if val > max_hour_val * 0.5:
                bar += "█"
            elif val > max_hour_val * 0.2:
                bar += "▓"
            elif val > 0:
                bar += "░"
            else:
                bar += "·"
        end_hour = (hrs["peak_window_start"] + 4) % 24
        print(f"  {bar}   "
              f"{_fmt_hour(hrs['peak_window_start'])}–{_fmt_hour(end_hour)} "
              f"({hrs['peak_window_pct']:.0f}% of {metric} tokens)")
        print(f"  {'0  3  6  9  12 15 18 21':<24}   "
              f"Busiest hour: {_fmt_hour(hrs['peak_hour'])} "
              f"({hrs['peak_hour_pct']:.0f}%)")

        wd_peak = max(hrs["weekday_hours"], key=hrs["weekday_hours"].get) if hrs["weekday_hours"] else 0
        we_peak = max(hrs["weekend_hours"], key=hrs["weekend_hours"].get) if hrs["weekend_hours"] else 0
        print(f"  {'':24}   "
              f"Weekday peak: {_fmt_hour(wd_peak)}   "
              f"Weekend peak: {_fmt_hour(we_peak)}")

    print()


def _build_heatmap_bars(hour_data: list, max_hour: int) -> str:
    """Build HTML for hourly heatmap bar elements."""
    bars = []
    for h in range(24):
        height = max(5, int(hour_data[h] / max_hour * 100)) if max_hour > 0 else 5
        opacity = max(0.15, hour_data[h] / max_hour) if max_hour > 0 else 0.15
        bars.append(
            f'<div class="heatmap-bar" style="height:{height}%;'
            f'background:rgba(78,121,167,{opacity:.2f})"></div>'
        )
    return "\n      ".join(bars)


def _build_heatmap_labels() -> str:
    """Build HTML for hourly heatmap hour labels."""
    labels = []
    for h in range(24):
        text = "" if h % 3 else _fmt_hour(h)
        labels.append(f"<span>{text}</span>")
    return "\n      ".join(labels)


def render_html_report(stats: dict, records: list, metric: str, days: int, output_path: str):
    """Generate a self-contained HTML report file."""
    br = stats["burn_rate"]
    sess = stats["sessions"]
    hrs = stats["hours"]
    mix = stats["model_mix"]
    proj = stats["projects"]
    cost = stats["cost"]

    # Build daily chart data for Chart.js
    day_totals = defaultdict(lambda: defaultdict(int))
    project_names = {p["name"] for p in proj}
    for r in records:
        val = _get_metric_value(r, metric)
        pname = r["project"] if r["project"] in project_names else "Other"
        day_totals[r["date"]][pname] += val

    sorted_dates = sorted(day_totals.keys())
    all_projects = sorted(project_names) + (["Other"] if any(
        r["project"] not in project_names for r in records
    ) else [])

    chart_datasets = []
    colors = [
        "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
        "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
        "#9c755f", "#bab0ac",
    ]
    for i, pname in enumerate(all_projects):
        data_points = [day_totals[d].get(pname, 0) for d in sorted_dates]
        chart_datasets.append({
            "label": pname,
            "data": data_points,
            "backgroundColor": colors[i % len(colors)],
        })

    # Hourly heatmap data
    hour_data = [hrs["hour_totals"].get(h, 0) for h in range(24)]
    max_hour = max(hour_data) if any(hour_data) else 1

    # Model mix for donut
    model_labels = [m["name"].capitalize() for m in mix["models"]]
    model_values = [m["total_tokens"] for m in mix["models"]]
    model_colors = ["#e15759", "#4e79a7", "#59a14f", "#f28e2b", "#76b7b2"][:len(model_labels)]

    trend_arrow = "&#x25B2;" if br["trend_pct"] > 0 else "&#x25BC;" if br["trend_pct"] < 0 else "&#x2500;"
    trend_sign = "+" if br["trend_pct"] > 0 else ""

    # Build model table rows
    model_rows = ""
    for m in mix["models"]:
        model_rows += (f'<tr><td>{m["name"].capitalize()}</td>'
                      f'<td>{_fmt_tokens(m["total_tokens"])}</td>'
                      f'<td>{m["pct"]:.0f}%</td>'
                      f'<td>{_fmt_cost(m["est_cost"])}</td></tr>\n')

    # Build project table rows
    project_rows = ""
    for p in proj:
        project_rows += (f'<tr><td>{p["name"]}</td>'
                        f'<td>{_fmt_tokens(p["total_tokens"])}</td>'
                        f'<td>{p["session_count"]}</td>'
                        f'<td>{p["primary_model"].capitalize()}</td>'
                        f'<td>{_fmt_cost(p["est_cost"])}</td></tr>\n')

    heatmap_bars = _build_heatmap_bars(hour_data, max_hour)
    heatmap_labels = _build_heatmap_labels()

    peak_end = (hrs["peak_window_start"] + 4) % 24

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Code Usage Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f7; color: #1d1d1f; padding: 2rem; }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #86868b; margin-bottom: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: white; border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card-label {{ font-size: 0.75rem; color: #86868b; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card-value {{ font-size: 1.5rem; font-weight: 600; margin-top: 0.25rem; }}
  .card-detail {{ font-size: 0.8rem; color: #86868b; margin-top: 0.25rem; }}
  .section {{ background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .section h2 {{ font-size: 1.1rem; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #f0f0f0; }}
  th {{ font-size: 0.75rem; color: #86868b; text-transform: uppercase; letter-spacing: 0.05em; }}
  .heatmap {{ display: flex; gap: 2px; align-items: flex-end; height: 60px; }}
  .heatmap-bar {{ flex: 1; border-radius: 2px 2px 0 0; min-width: 0; }}
  .heatmap-labels {{ display: flex; gap: 2px; font-size: 0.65rem; color: #86868b; }}
  .heatmap-labels span {{ flex: 1; text-align: center; }}
  .chart-container {{ position: relative; height: 300px; }}
  .donut-container {{ position: relative; height: 200px; width: 200px; margin: 0 auto; }}
  .model-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; align-items: start; }}
</style>
</head>
<body>
<div class="container">
  <h1>Claude Code Usage Report</h1>
  <p class="subtitle">Last {days} days &middot; {_fmt_tokens(br['total'])} {metric} tokens &middot; Est. API cost: {_fmt_cost(cost['total'])}</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Daily Average</div>
      <div class="card-value">{_fmt_tokens(br['daily_avg'])}</div>
      <div class="card-detail">Weekday: {_fmt_tokens(br['weekday_avg'])} &middot; Weekend: {_fmt_tokens(br['weekend_avg'])}</div>
    </div>
    <div class="card">
      <div class="card-label">Weekly Average</div>
      <div class="card-value">{_fmt_tokens(br['weekly_avg'])}</div>
      <div class="card-detail">Trend: {trend_arrow} {trend_sign}{br['trend_pct']:.0f}% vs prior</div>
    </div>
    <div class="card">
      <div class="card-label">Sessions</div>
      <div class="card-value">{sess['count']}</div>
      <div class="card-detail">Avg: {_fmt_tokens(int(sess['avg']))}/session</div>
    </div>
    <div class="card">
      <div class="card-label">Est. API Cost</div>
      <div class="card-value">{_fmt_cost(cost['total'])}</div>
      <div class="card-detail">{_fmt_cost(cost['per_day_avg'])}/day</div>
    </div>
  </div>

  <div class="section">
    <h2>Daily Usage</h2>
    <div class="chart-container"><canvas id="dailyChart"></canvas></div>
  </div>

  <div class="section">
    <div class="model-grid">
      <div>
        <h2>Model Mix</h2>
        <div class="donut-container"><canvas id="modelChart"></canvas></div>
      </div>
      <div>
        <h2>Cost by Model</h2>
        <table>
          <tr><th>Model</th><th>Tokens</th><th>Share</th><th>Est. Cost</th></tr>
          {model_rows}
        </table>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Top Projects</h2>
    <table>
      <tr><th>Project</th><th>Tokens</th><th>Sessions</th><th>Primary Model</th><th>Est. Cost</th></tr>
      {project_rows}
    </table>
  </div>

  <div class="section">
    <h2>Usage by Hour</h2>
    <div class="heatmap">
      {heatmap_bars}
    </div>
    <div class="heatmap-labels">
      {heatmap_labels}
    </div>
    <p style="margin-top:0.75rem;font-size:0.85rem;color:#86868b">
      Peak: {_fmt_hour(hrs['peak_window_start'])}&ndash;{_fmt_hour(peak_end)} ({hrs['peak_window_pct']:.0f}%) &middot;
      Busiest: {_fmt_hour(hrs['peak_hour'])} ({hrs['peak_hour_pct']:.0f}%)
    </p>
  </div>
</div>

<script>
const dailyCtx = document.getElementById('dailyChart').getContext('2d');
new Chart(dailyCtx, {{
  type: 'bar',
  data: {{
    labels: {_json.dumps(sorted_dates)},
    datasets: {_json.dumps(chart_datasets)}
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{
      x: {{ stacked: true }},
      y: {{ stacked: true, ticks: {{ callback: v => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v }} }}
    }},
    plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }} }}
  }}
}});

const modelCtx = document.getElementById('modelChart').getContext('2d');
new Chart(modelCtx, {{
  type: 'doughnut',
  data: {{
    labels: {_json.dumps(model_labels)},
    datasets: [{{ data: {_json.dumps(model_values)}, backgroundColor: {_json.dumps(model_colors)} }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report saved to {output_path}", file=sys.stderr)
