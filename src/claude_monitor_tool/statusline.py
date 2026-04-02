"""Statusline mode — 2-line output for Claude Code integration (from Repo 2 pattern).

This produces a compact 2-line output suitable for embedding in Claude Code's
statusLine configuration. Zero external dependencies beyond this package.
"""

from __future__ import annotations

import json
import sys

from claude_monitor_tool.data.api_client import ApiClient
from claude_monitor_tool.tui.theme import BAR_CRIT, BAR_LOW, BAR_MED, GREEN, RED, YELLOW


# ANSI color codes for statusline (no Rich markup here)
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"

_FILLED = "\u25b0"  # ▰
_EMPTY = "\u25b1"   # ▱


def _color_pct(pct: float) -> str:
    if pct >= 90:
        return _RED
    if pct >= 70:
        return _YELLOW
    return _GREEN


def _gauge(pct: float, blocks: int = 5) -> str:
    filled = round(min(100, max(0, pct)) / 100 * blocks)
    color = _color_pct(pct)
    return f"{color}{_FILLED * filled}{_DIM}{_EMPTY * (blocks - filled)}{_RESET}"


def _format_reset(minutes: float) -> str:
    if minutes <= 0:
        return ""
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def _compact(n: int | float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(int(n))


def run_statusline() -> None:
    """Main entry point for statusline mode. Reads stdin, outputs 2 lines."""
    # Ensure UTF-8 on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # Parse session data from stdin
    session = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            session = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        pass

    # Line 1: Model + project
    model = session.get("model", {}).get("display_name", "Claude")
    project = session.get("workspace", {}).get("project_dir", "")
    if project:
        project = project.split("/")[-1].split("\\")[-1]

    line1_parts = [f"{_CYAN}◆ {model}{_RESET}"]
    if project:
        line1_parts.append(f"{_DIM}│{_RESET} {project}")
    line1 = " ".join(line1_parts)

    # Line 2: Quotas + tokens + duration
    line2_parts = []

    # Context window
    ctx = session.get("context_window", {})
    ctx_pct = float(ctx.get("used_percentage", 0))
    if ctx_pct > 0:
        line2_parts.append(f"{_gauge(ctx_pct)} {_color_pct(ctx_pct)}{ctx_pct:.0f}%{_RESET}")

    # Token counts
    input_tok = int(ctx.get("total_input_tokens", 0))
    output_tok = int(ctx.get("total_output_tokens", 0))
    if input_tok or output_tok:
        line2_parts.append(f"↑{_compact(input_tok)} ↓{_compact(output_tok)}")

    # API quotas
    api = ApiClient()
    quota = api.get_quota()
    if quota:
        h5_remaining = 100 - quota.five_hour_used_pct
        reset_str = _format_reset(quota.five_hour_reset_minutes)
        line2_parts.append(
            f"5h: {_gauge(quota.five_hour_used_pct)} "
            f"{_color_pct(quota.five_hour_used_pct)}{h5_remaining:.0f}%{_RESET}"
            f"{f' ({reset_str})' if reset_str else ''}"
        )

        if quota.seven_day_used_pct > 0:
            d7_remaining = 100 - quota.seven_day_used_pct
            line2_parts.append(
                f"7d: {_gauge(quota.seven_day_used_pct)} "
                f"{_color_pct(quota.seven_day_used_pct)}{d7_remaining:.0f}%{_RESET}"
            )

    # Duration
    cost_data = session.get("cost", {})
    duration_ms = int(cost_data.get("total_duration_ms", 0))
    if duration_ms > 0:
        total_sec = duration_ms // 1000
        h = total_sec // 3600
        m = (total_sec % 3600) // 60
        s = total_sec % 60
        dur_str = f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"
        line2_parts.append(f"{_DIM}{dur_str}{_RESET}")

    # Cost
    cost_usd = float(cost_data.get("total_cost_usd", 0))
    if cost_usd > 0:
        line2_parts.append(f"{_DIM}${cost_usd:.2f}{_RESET}")

    line2 = " │ ".join(line2_parts) if line2_parts else f"{_DIM}waiting...{_RESET}"

    print(line1)
    print(line2)
