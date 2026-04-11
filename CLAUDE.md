# Claude Usage Chart

## Tech Stack
- Python 3.9+ (stdlib only, no required dependencies)
- matplotlib (declared via PEP 723 inline script metadata; auto-installed by `uv run`)
- CLI entry point: `claude-usage-chart.py`
- Analytics engine: `claude_usage_analytics.py`
- Helper script: `generate_example.py` (generates fake chart for README)

## Project Structure
```
claude-usage-chart/
├── claude-usage-chart.py        — CLI entry point, JSONL parser, chart renderers
├── claude_usage_analytics.py    — Analytics engine + report renderers
├── generate_example.py          — Generates fake example.png for README
├── example.png                  — Fake chart image used in README
├── tests/
│   ├── conftest.py              — Shared test fixtures (synthetic records)
│   └── test_analytics.py        — Analytics unit tests (40 tests)
├── LICENSE                      — MIT
└── README.md                    — Includes setup guide for /burn slash command
```

## How It Works
1. Scans `~/.claude/projects/*/*.jsonl` for Claude Code session transcripts
2. Parses assistant messages with `message.usage` token counts
3. Derives project names from `cwd` field, groups worktrees with parent projects
4. Aggregates by day × project, ranks top N, buckets rest as "Other"
5. Renders stacked bar chart (matplotlib or ANSI terminal fallback)

## Key Functions

### claude-usage-chart.py (CLI + charts)
- `derive_project_name(cwd)` — extracts short name, strips worktree paths
- `parse_all_transcripts(base_dir, cutoff)` — yields usage records from JSONL
- `aggregate(records, days, top_n, metric)` — builds chart-ready data matrix
- `chart_matplotlib(...)` — stacked bar chart with daily totals and grand total
- `chart_terminal(...)` — ANSI colored horizontal bars fallback

### claude_usage_analytics.py (analytics + reports)
- `compute_burn_rate()` — daily/weekly/weekday/weekend averages, trend
- `compute_session_stats()` — session count, avg, median, largest
- `compute_hourly_breakdown()` — 24h heatmap, peak windows
- `compute_model_mix()` — token/cost breakdown by model
- `compute_project_rankings()` — top N projects with stats
- `compute_api_cost()` — equivalent API cost estimates
- `render_terminal_report()` — ANSI-formatted terminal summary
- `render_html_report()` — self-contained HTML dashboard with Chart.js

## JSONL Data Format
- Timestamps: ISO 8601 UTC (`2026-03-08T17:15:12.034Z`)
- Usage fields: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- Worktree marker in cwd: `/.claude/worktrees/`

## Dev Workflow
- Run with: `uv run claude-usage-chart.py`
- Test terminal: `python3 claude-usage-chart.py --terminal --days 7`
- Analytics report: `python3 claude-usage-chart.py --report --days 7`
- HTML report: `python3 claude-usage-chart.py --html report.html --days 7`
- Cost overlay: `python3 claude-usage-chart.py --terminal --days 7 --cost`
- Run tests: `python3 -m pytest tests/ -v`
- Generate example: `uv run generate_example.py`

## Code Search
This project is indexed with codebase-memory-mcp. Use `search_code` and `query_graph` tools to explore the codebase.

## Git
- Remote: https://github.com/gdilla/claude-usage-chart
- Branch: main
- Commit messages: descriptive, conventional style

## Common Mistakes
<!-- When Claude makes a mistake and you correct it, say "Add that to CLAUDE.md Common Mistakes" to build project-specific rules over time -->
