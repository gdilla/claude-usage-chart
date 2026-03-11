#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib"]
# ///
"""Generate a fake example chart for the README."""
import random
from datetime import datetime, timedelta

# Fake projects and their relative weights
PROJECTS = [
    ("my-saas-app", 0.30),
    ("api-server", 0.20),
    ("mobile-app", 0.15),
    ("infra", 0.10),
    ("design-system", 0.08),
    ("docs-site", 0.07),
    ("cli-tool", 0.05),
    ("Other", 0.05),
]

def main():
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    random.seed(42)
    days = 21
    dates = [datetime.now() - timedelta(days=days - 1 - i) for i in range(days)]

    # Generate fake data with realistic patterns (lower on weekends, ramp up mid-week)
    data = {}
    for project, weight in PROJECTS:
        values = []
        for d in dates:
            base = random.gauss(400_000 * weight, 80_000 * weight)
            # Weekend dip
            if d.weekday() >= 5:
                base *= 0.3
            # Some random spikes
            if random.random() < 0.1:
                base *= 2.5
            values.append(max(0, int(base)))
        data[project] = values

    projects = [p for p, _ in PROJECTS]

    fig, ax = plt.subplots(figsize=(14, 6))
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i / max(len(projects), 1)) for i in range(len(projects))]

    bottom = [0] * days
    for i, project in enumerate(projects):
        values = data[project]
        ax.bar(dates, values, bottom=bottom, label=project,
               color=colors[i], width=0.8, edgecolor="white", linewidth=0.3)
        bottom = [b + v for b, v in zip(bottom, values)]

    # Daily total labels
    for i, (x, total) in enumerate(zip(dates, bottom)):
        if total > 0:
            fmt = f"{total / 1_000_000:.1f}M" if total >= 1_000_000 else f"{total / 1_000:.0f}K"
            ax.text(x, total, fmt, ha="center", va="bottom", fontsize=6, color="#444444")

    grand_total = sum(bottom)
    fmt_total = f"{grand_total / 1_000_000:.1f}M"
    date_range = f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}"
    ax.set_title(
        f"Claude Code Token Usage (output tokens)\n{date_range}  ·  Total: {fmt_total}",
        fontsize=14, fontweight="bold")
    ax.set_ylabel("Tokens")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, _: f"{x / 1_000_000:.1f}M" if x >= 1_000_000 else f"{int(x / 1_000)}K" if x >= 1_000 else str(int(x))))

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate(rotation=45)

    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    plt.tight_layout()

    fig.savefig("example.png", dpi=150, bbox_inches="tight")
    print("Saved example.png")

if __name__ == "__main__":
    main()
