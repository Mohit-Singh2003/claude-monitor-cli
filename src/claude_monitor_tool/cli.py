"""CLI entry point — argument parsing and mode dispatch."""

from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-monitor",
        description="Interactive terminal monitor for Claude AI usage.",
    )
    p.add_argument(
        "--plan",
        choices=["pro", "max5", "max20", "custom"],
        default="pro",
        help="Subscription plan (default: pro)",
    )
    p.add_argument(
        "--view",
        choices=["realtime", "daily", "monthly", "sessions"],
        default="realtime",
        help="Initial view (default: realtime)",
    )
    p.add_argument(
        "--refresh-rate",
        type=int,
        default=10,
        help="Data refresh interval in seconds (default: 10)",
    )
    p.add_argument(
        "--statusline",
        action="store_true",
        help="Output 2-line statusline for Claude Code integration",
    )
    p.add_argument(
        "--export",
        choices=["csv", "json"],
        help="Export usage data to stdout",
    )
    p.add_argument(
        "--hours",
        type=int,
        default=192,
        help="Hours of history to load (default: 192)",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    p.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version",
    )
    return p


def _run_export(fmt: str, hours: int) -> None:
    """Export usage data to stdout."""
    from claude_monitor_tool.data.reader import JsonlReader
    from claude_monitor_tool.data.session_analyzer import SessionAnalyzer

    reader = JsonlReader()
    entries = reader.read_entries(hours=hours)

    if not entries:
        print("No usage data found.", file=sys.stderr)
        sys.exit(1)

    analyzer = SessionAnalyzer()
    daily = analyzer.get_daily_stats(entries)

    if fmt == "json":
        import json
        print(json.dumps(daily, indent=2, default=str))
    elif fmt == "csv":
        import csv
        import io

        out = io.StringIO()
        if daily:
            writer = csv.DictWriter(out, fieldnames=daily[0].keys())
            writer.writeheader()
            for row in daily:
                row_copy = dict(row)
                if isinstance(row_copy.get("models"), list):
                    row_copy["models"] = ", ".join(row_copy["models"])
                writer.writerow(row_copy)
        print(out.getvalue())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.version:
        from claude_monitor_tool import __version__
        print(f"claude-monitor-tool {__version__}")
        sys.exit(0)

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    if args.statusline:
        from claude_monitor_tool.statusline import run_statusline
        run_statusline()
        sys.exit(0)

    if args.export:
        _run_export(args.export, args.hours)
        sys.exit(0)

    # Launch TUI
    from claude_monitor_tool.models import Plan
    from claude_monitor_tool.tui.app import ClaudeMonitorApp

    plan = Plan(args.plan)
    app = ClaudeMonitorApp(plan=plan)
    app._refresh_interval = args.refresh_rate
    app.run()


if __name__ == "__main__":
    main()
