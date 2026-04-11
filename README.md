# Claude Code Usage Chart

Visualize your [Claude Code](https://claude.ai/claude-code) token usage broken down by day and project — with optional analytics reports covering burn rate, session stats, hourly patterns, model mix, and estimated API costs.

![Example chart](example.png)

## Quick Start

```bash
# Clone
git clone https://github.com/gdilla/claude-usage-chart.git
cd claude-usage-chart

# Terminal chart (no dependencies needed)
python3 claude-usage-chart.py --terminal

# Graphical chart (uv reads dependencies from script metadata)
uv run claude-usage-chart.py
```

## How It Works

Claude Code stores session transcripts as JSONL files in `~/.claude/projects/`. This tool:

1. Scans all `~/.claude/projects/*/*.jsonl` files
2. Extracts token usage from assistant messages (input, output, cache creation, cache read)
3. Derives project names from `cwd` fields; groups worktrees with their parent project
4. Aggregates by day × project, ranks top N, buckets the rest as "Other"
5. Renders a stacked bar chart (matplotlib GUI, PNG, or ANSI terminal fallback)

For analytics mode (`--report` / `--html`), it also computes:
- **Burn rate** — daily/weekly averages, weekday vs weekend, 7-day trend direction
- **Session stats** — count, average/median length, largest session
- **Hourly breakdown** — 24-hour heatmap with peak usage windows
- **Model mix** — token and cost breakdown by model (Opus, Sonnet, Haiku)
- **Project rankings** — top projects by volume with session counts
- **API cost estimates** — what your usage would cost at Anthropic API rates

## Options

### Chart Options

| Flag | Default | Description |
|------|---------|-------------|
| `--days N` | 30 | How far back to look |
| `--top N` | 8 | Top N projects by volume (rest grouped as "Other") |
| `--metric` | output | Token type: `output`, `input`, `total`, or `cache` |
| `--output PATH` | — | Save chart as PNG instead of displaying |
| `--terminal` | — | Force terminal chart (ANSI colored bars) |
| `--project NAME` | — | Filter to a specific project (name or cwd path) |
| `--cost` | — | Overlay estimated API cost per day on the chart |

### Analytics Options

| Flag | Default | Description |
|------|---------|-------------|
| `--report` | — | Print a detailed analytics report to the terminal |
| `--html PATH` | — | Generate a self-contained HTML dashboard (Chart.js) |
| `--sessions` | — | Show session count and peak hours summary |

## Examples

```bash
# Last 7 days, top 5 projects
uv run claude-usage-chart.py --days 7 --top 5

# Total tokens (input + output) for the last 2 weeks
uv run claude-usage-chart.py --days 14 --metric total

# Save to file
uv run claude-usage-chart.py --output usage.png

# Terminal chart with cost overlay
python3 claude-usage-chart.py --terminal --days 7 --cost

# Analytics report in terminal
python3 claude-usage-chart.py --report --days 7

# HTML dashboard
python3 claude-usage-chart.py --html report.html --days 7

# Session stats with peak hours
python3 claude-usage-chart.py --sessions --days 14
```

## Use as a Claude Code Slash Command

You can set this up as a `/burn` command so you (or your team) can type `/burn` inside any Claude Code session to instantly see a usage chart.

### Setup

1. Clone this repo somewhere on your machine:
   ```bash
   git clone https://github.com/gdilla/claude-usage-chart.git ~/projects/claude-usage-chart
   ```

2. Create the global commands directory (if it doesn't exist):
   ```bash
   mkdir -p ~/.claude/commands
   ```

3. Create `~/.claude/commands/burn.md` with this content:
   ```markdown
   Show my Claude Code token usage chart.

   ## Instructions

   Run the token usage chart script with these defaults, overridden by any arguments provided:

   ```
   uv run ~/projects/claude-usage-chart/claude-usage-chart.py --output /tmp/usage.png --days 30 $ARGUMENTS
   ```

   Then open the resulting PNG with `open /tmp/usage.png`.

   If the user passes arguments like `--days 7`, `--top 5`, `--metric total`, `--terminal`, etc.,
   append them to the command. If `--terminal` is passed, skip the `--output` flag and don't try
   to open a PNG.

   After running, briefly summarize what the chart shows (total tokens, top project, date range).
   ```

   > **Note:** This requires [uv](https://docs.astral.sh/uv/). If you don't have it, install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

### Usage in Claude Code

```
/burn                              # 30-day chart, opens in Preview
/burn --days 7                     # last week
/burn --days 14 --top 5            # 2 weeks, top 5 projects
/burn --terminal                   # quick terminal view, no image
/burn --terminal --cost            # terminal view with cost overlay
/burn --metric total --days 7      # total tokens (input + output)
/burn --report                     # full analytics report in terminal
/burn --html /tmp/report.html      # open HTML dashboard in browser
/burn --this                       # chart for the current project only
/burn --this --days 14             # current project, last 2 weeks
/burn --this --terminal            # current project, terminal view
```

> **Tip:** `--this` is a shortcut that filters the chart to whatever project you're working in. Under the hood it passes `--project <your cwd>` to the script.

## Requirements

- **[uv](https://docs.astral.sh/uv/)** — manages Python and dependencies automatically
- **Python 3.9+** (uses only stdlib; uv will install Python if needed)
- **matplotlib** (optional — for graphical charts; falls back to terminal output; auto-installed when run via `uv run`)

## License

MIT
