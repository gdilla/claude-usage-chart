# Claude Usage Chart

## Tech Stack
- Python 3.9+ (stdlib only, no required dependencies)
- matplotlib (declared via PEP 723 inline script metadata; auto-installed by `uv run`)
- Single-file CLI script: `claude-usage-chart.py`
- Helper script: `generate_example.py` (generates fake chart for README)

## Project Structure
```
claude-usage-chart/
├── claude-usage-chart.py   — Main CLI script (all logic in one file)
├── generate_example.py     — Generates fake example.png for README
├── example.png             — Fake chart image used in README
├── LICENSE                 — MIT
└── README.md               — Includes setup guide for /burn slash command
```

## How It Works
1. Scans `~/.claude/projects/*/*.jsonl` for Claude Code session transcripts
2. Parses assistant messages with `message.usage` token counts
3. Derives project names from `cwd` field, groups worktrees with parent projects
4. Aggregates by day × project, ranks top N, buckets rest as "Other"
5. Renders stacked bar chart (matplotlib or ANSI terminal fallback)

## Key Functions
- `derive_project_name(cwd)` — extracts short name, strips worktree paths
- `parse_all_transcripts(base_dir, cutoff)` — yields usage records from JSONL
- `aggregate(records, days, top_n, metric)` — builds chart-ready data matrix
- `chart_matplotlib(...)` — stacked bar chart with daily totals and grand total
- `chart_terminal(...)` — ANSI colored horizontal bars fallback

## JSONL Data Format
- Timestamps: ISO 8601 UTC (`2026-03-08T17:15:12.034Z`)
- Usage fields: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- Worktree marker in cwd: `/.claude/worktrees/`

## Dev Workflow
- Run with: `uv run claude-usage-chart.py`
- Test terminal: `python3 claude-usage-chart.py --terminal --days 7`
- Generate example: `uv run generate_example.py`

## Code Search
This project is indexed with codebase-memory-mcp. Use `search_code` and `query_graph` tools to explore the codebase.

## Git
- Remote: https://github.com/gdilla/claude-usage-chart
- Branch: main
- Commit messages: descriptive, conventional style

## Common Mistakes
<!-- When Claude makes a mistake and you correct it, say "Add that to CLAUDE.md Common Mistakes" to build project-specific rules over time -->
