"""Formatting helpers for display values."""

from __future__ import annotations


def compact_number(n: int | float) -> str:
    """Format numbers compactly: 1234567 -> 1.2m, 12345 -> 12.3k"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def format_duration_short(minutes: float) -> str:
    """Format minutes to compact duration: 142 -> 2h 22m"""
    if minutes <= 0:
        return "0m"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def format_cost(cost: float) -> str:
    """Format USD cost."""
    if cost >= 10:
        return f"${cost:.2f}"
    if cost >= 1:
        return f"${cost:.2f}"
    return f"${cost:.4f}"


def format_tokens(n: int) -> str:
    """Format token count with commas."""
    return f"{n:,}"
