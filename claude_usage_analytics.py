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
