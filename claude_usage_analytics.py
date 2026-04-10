"""Analytics engine for Claude Code token usage.

Pure functions: records in, stats out. No CLI logic.
"""

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
