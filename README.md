# Claude Monitor Tool

Interactive terminal monitor for Claude AI usage — real-time quotas, burn rate, cost analytics, and ML predictions.

## Install

```bash
# From PyPI
pip install claude-monitor-cli

# From source
git clone https://github.com/Mohit-Singh2003/claude-monitor-cli.git
cd claude-monitor-cli
pip install -e .
```

## Usage

```bash
# Interactive TUI (default)
claude-monitor

# Specify your plan
claude-monitor --plan pro       # Pro ($20/mo)
claude-monitor --plan max5      # Max ($100/mo)
claude-monitor --plan max20     # Max ($200/mo)

# Statusline mode (2-line output for Claude Code integration)
claude-monitor --statusline

# Export data
claude-monitor --export json
claude-monitor --export csv

# Debug mode
claude-monitor --debug
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `r` | Realtime dashboard |
| `d` | Daily usage table |
| `m` | Monthly usage table |
| `s` | Session history |
| `F5` | Force refresh |
| `q` | Quit |

## Features

- **Real-time quota tracking** — 5-hour and 7-day utilization from Anthropic's API
- **Local session analysis** — parses Claude Code JSONL logs for detailed token breakdowns
- **Burn rate analytics** — tokens/min, cost/min, pace indicator
- **P90 predictions** — ML-based limit detection from historical usage
- **Sparkline trends** — 12-hour inline token charts
- **Model breakdown** — per-model (Opus/Sonnet/Haiku) usage distribution
- **Multiple views** — realtime dashboard, daily table, monthly table, session history
- **Statusline mode** — compact 2-line output for Claude Code's status bar
- **CSV/JSON export** — dump usage data for external analysis
- **Claude-native theme** — purple/slate color palette matching Claude Code's aesthetic

## Data Sources

This tool reads from two sources, both on your local machine:

1. **JSONL files** at `~/.claude/projects/` — Claude Code's local session logs (offline, read-only)
2. **Anthropic OAuth API** at `api.anthropic.com/api/oauth/usage` — real-time quota percentages (uses Claude Code's own OAuth token)

No API key required. No data sent to third parties. See [SECURITY.md](SECURITY.md) for full details.

## Requirements

- Python 3.10+
- Claude Code installed and logged in (for data to exist)

## License

MIT
