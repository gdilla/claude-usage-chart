#!/usr/bin/env python3
"""Visualize Claude Code token usage by day and project.

Scans ~/.claude/projects/*/*.jsonl, extracts token usage from assistant
messages, and produces a stacked bar chart (matplotlib or terminal fallback).

Usage:
    python3 claude-usage-chart.py                      # last 30 days, top 8 projects
    python3 claude-usage-chart.py --days 7 --top 5     # last week, top 5
    python3 claude-usage-chart.py --metric total        # input + output tokens
    python3 claude-usage-chart.py --output usage.png    # save to file
    python3 claude-usage-chart.py --terminal            # force terminal chart
"""

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def derive_project_name(cwd: str) -> str:
    """Extract a short project name from a cwd path, grouping worktrees with parents."""
    if not cwd:
        return "unknown"

    # Strip worktree suffix: /foo/bar/.claude/worktrees/fix-tables -> /foo/bar
    worktree_marker = "/.claude/worktrees/"
    idx = cwd.find(worktree_marker)
    if idx != -1:
        cwd = cwd[:idx]

    # Also handle --claude-worktrees- suffix in encoded directory names
    wt_marker = "--claude-worktrees-"
    idx = cwd.find(wt_marker)
    if idx != -1:
        cwd = cwd[:idx]

    # Take the last path component as the project name
    return os.path.basename(cwd.rstrip("/")) or "unknown"


def parse_all_transcripts(base_dir: str, cutoff_date: datetime):
    """Yield usage records from all JSONL transcript files.

    Each yielded record is a dict:
        {date: str, project: str, input_tokens: int, output_tokens: int,
         cache_creation_input_tokens: int, cache_read_input_tokens: int}
    """
    pattern = os.path.join(base_dir, "*", "*.jsonl")
    files = glob.glob(pattern)

    for filepath in files:
        try:
            with open(filepath, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if record.get("type") != "assistant":
                        continue

                    message = record.get("message")
                    if not isinstance(message, dict):
                        continue

                    usage = message.get("usage")
                    if not isinstance(usage, dict):
                        continue

                    # Parse timestamp to local date
                    ts_str = record.get("timestamp", "")
                    if not ts_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue

                    if ts < cutoff_date:
                        continue

                    local_date = ts.astimezone().strftime("%Y-%m-%d")
                    cwd = record.get("cwd", "")
                    project = derive_project_name(cwd)

                    yield {
                        "date": local_date,
                        "project": project,
                        "input_tokens": usage.get("input_tokens", 0) or 0,
                        "output_tokens": usage.get("output_tokens", 0) or 0,
                        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0) or 0,
                        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0) or 0,
                    }
        except (OSError, IOError):
            continue


def get_metric_value(rec: dict, metric: str) -> int:
    """Extract the relevant token count based on the chosen metric."""
    if metric == "output":
        return rec["output_tokens"]
    elif metric == "input":
        return rec["input_tokens"]
    elif metric == "cache":
        return rec["cache_creation_input_tokens"] + rec["cache_read_input_tokens"]
    else:  # total
        return rec["input_tokens"] + rec["output_tokens"]


def aggregate(records, days: int, top_n: int, metric: str):
    """Aggregate records into chart-ready data.

    Returns:
        dates: sorted list of date strings
        projects: ordered list of project names (top N + "Other")
        data: dict mapping project -> list of values per date
    """
    # Build per-day, per-project totals
    totals = defaultdict(lambda: defaultdict(int))  # date -> project -> value
    project_totals = defaultdict(int)

    for rec in records:
        val = get_metric_value(rec, metric)
        totals[rec["date"]][rec["project"]] += val
        project_totals[rec["project"]] += val

    # Determine top N projects
    ranked = sorted(project_totals.items(), key=lambda x: x[1], reverse=True)
    top_projects = [name for name, _ in ranked[:top_n]]
    other_projects = {name for name, _ in ranked[top_n:]}

    # Build continuous date range
    today = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    dates = []
    d = datetime.strptime(start, "%Y-%m-%d")
    end = datetime.strptime(today, "%Y-%m-%d")
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    # Build data matrix
    projects = top_projects + (["Other"] if other_projects else [])
    data = {p: [] for p in projects}

    for date in dates:
        day_data = totals.get(date, {})
        for p in top_projects:
            data[p].append(day_data.get(p, 0))
        if other_projects:
            other_val = sum(day_data.get(p, 0) for p in other_projects)
            data["Other"].append(other_val)

    return dates, projects, data


def format_tokens(n: int) -> str:
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def chart_matplotlib(dates, projects, data, metric, output_path=None):
    """Render a stacked bar chart using matplotlib."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not available, falling back to terminal chart.", file=sys.stderr)
        chart_terminal(dates, projects, data, metric)
        return

    fig, ax = plt.subplots(figsize=(max(12, len(dates) * 0.4), 6))
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i / max(len(projects), 1)) for i in range(len(projects))]

    x_dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
    bottom = [0] * len(dates)

    for i, project in enumerate(projects):
        values = data[project]
        ax.bar(x_dates, values, bottom=bottom, label=project,
               color=colors[i], width=0.8, edgecolor="white", linewidth=0.3)
        bottom = [b + v for b, v in zip(bottom, values)]

    # Add daily total labels on top of each bar
    for i, (x, total) in enumerate(zip(x_dates, bottom)):
        if total > 0:
            ax.text(x, total, format_tokens(total), ha="center", va="bottom",
                    fontsize=6, color="#444444")

    grand_total = sum(bottom)
    date_range = f"{dates[0]} to {dates[-1]}" if len(dates) > 1 else dates[0]
    ax.set_title(
        f"Claude Code Token Usage ({metric} tokens)\n"
        f"{date_range}  ·  Total: {format_tokens(grand_total)}",
        fontsize=14, fontweight="bold")
    ax.set_ylabel("Tokens")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: format_tokens(int(x))))

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 15)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate(rotation=45)

    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved to {output_path}")
    else:
        plt.show()


# Terminal color palette (ANSI 256-color)
TERM_COLORS = [
    196, 46, 33, 208, 129, 51, 226, 201,  # bright distinct colors
    82, 160, 75, 214, 99, 170, 39, 220,
]


def chart_terminal(dates, projects, data, metric):
    """Render a horizontal stacked bar chart in the terminal using ANSI colors."""
    term_width = min(os.get_terminal_size().columns, 120) if sys.stdout.isatty() else 80
    label_width = 10
    bar_width = term_width - label_width - 2

    # Find max daily total for scaling
    daily_totals = []
    for i in range(len(dates)):
        total = sum(data[p][i] for p in projects)
        daily_totals.append(total)
    max_total = max(daily_totals) if daily_totals else 1

    # Print legend
    print(f"\n  Claude Code Token Usage ({metric} tokens)")
    print(f"  {'─' * (term_width - 4)}")
    legend_parts = []
    for i, project in enumerate(projects):
        color = TERM_COLORS[i % len(TERM_COLORS)]
        total = sum(data[project])
        legend_parts.append(f"  \033[48;5;{color}m  \033[0m {project} ({format_tokens(total)})")
    # Print legend in rows of 3
    for i in range(0, len(legend_parts), 3):
        print("".join(legend_parts[i:i + 3]))
    print()

    # Print bars
    for i, date in enumerate(dates):
        # Format date label as "Mon DD"
        dt = datetime.strptime(date, "%Y-%m-%d")
        label = dt.strftime("%b %d")
        total = daily_totals[i]

        bar = ""
        remaining_width = bar_width
        for j, project in enumerate(projects):
            val = data[project][i]
            if val == 0 or max_total == 0:
                continue
            seg_width = max(1, round(val / max_total * bar_width)) if val > 0 else 0
            seg_width = min(seg_width, remaining_width)
            color = TERM_COLORS[j % len(TERM_COLORS)]
            bar += f"\033[48;5;{color}m{' ' * seg_width}\033[0m"
            remaining_width -= seg_width

        total_str = format_tokens(total)
        print(f"  {label:>{label_width}} {bar} {total_str}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Visualize Claude Code token usage by day and project."
    )
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days to look back (default: 30)")
    parser.add_argument("--top", type=int, default=8,
                        help="Show top N projects, rest grouped as Other (default: 8)")
    parser.add_argument("--metric", choices=["output", "input", "total", "cache"],
                        default="output",
                        help="Token metric to chart (default: output)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save chart to PNG file instead of displaying")
    parser.add_argument("--terminal", action="store_true",
                        help="Force terminal chart even if matplotlib is available")
    args = parser.parse_args()

    base_dir = os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(base_dir):
        print(f"Error: {base_dir} not found.", file=sys.stderr)
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    print(f"Scanning transcripts (last {args.days} days)...", file=sys.stderr)
    records = list(parse_all_transcripts(base_dir, cutoff))
    print(f"Found {len(records):,} assistant messages.", file=sys.stderr)

    if not records:
        print("No usage data found.", file=sys.stderr)
        sys.exit(0)

    dates, projects, data = aggregate(records, args.days, args.top, args.metric)

    total_tokens = sum(sum(data[p]) for p in projects)
    print(f"Total {args.metric} tokens: {format_tokens(total_tokens)}", file=sys.stderr)

    if args.terminal:
        chart_terminal(dates, projects, data, args.metric)
    elif args.output:
        chart_matplotlib(dates, projects, data, args.metric, output_path=args.output)
    else:
        # Try matplotlib, fall back to terminal
        try:
            import matplotlib
            chart_matplotlib(dates, projects, data, args.metric)
        except ImportError:
            chart_terminal(dates, projects, data, args.metric)


if __name__ == "__main__":
    main()
