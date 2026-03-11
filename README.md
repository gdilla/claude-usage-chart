# Claude Code Usage Chart

Visualize your [Claude Code](https://claude.ai/claude-code) token usage broken down by day and project.

![Example chart](https://github.com/user-attachments/assets/placeholder.png)

## Quick Start

```bash
# Clone
git clone https://github.com/gdilla/claude-usage-chart.git
cd claude-usage-chart

# Terminal chart (no dependencies needed)
python3 claude-usage-chart.py --terminal

# Graphical chart (requires matplotlib)
pip install matplotlib
python3 claude-usage-chart.py

# Or use uv to run without installing anything
uv run --with matplotlib python3 claude-usage-chart.py
```

## How It Works

Claude Code stores session transcripts as JSONL files in `~/.claude/projects/`. This script:

1. Scans all `~/.claude/projects/*/*.jsonl` files
2. Extracts token usage from assistant messages
3. Groups usage by day and project (worktrees are grouped with their parent project)
4. Renders a stacked bar chart

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--days N` | 30 | How far back to look |
| `--top N` | 8 | Top N projects by volume (rest grouped as "Other") |
| `--metric` | output | Token type: `output`, `input`, `total`, or `cache` |
| `--output PATH` | — | Save chart as PNG instead of displaying |
| `--terminal` | — | Force terminal chart (ANSI colored bars) |

## Examples

```bash
# Last 7 days, top 5 projects
python3 claude-usage-chart.py --days 7 --top 5

# Total tokens (input + output) for the last 2 weeks
python3 claude-usage-chart.py --days 14 --metric total

# Save to file
python3 claude-usage-chart.py --output usage.png
```

## Requirements

- **Python 3.9+** (uses only stdlib)
- **matplotlib** (optional — for graphical charts; falls back to terminal output)

## License

MIT
