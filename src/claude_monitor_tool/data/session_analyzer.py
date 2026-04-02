"""Session analyzer — groups usage entries into 5-hour session blocks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from claude_monitor_tool.models import SessionBlock, UsageEntry

SESSION_HOURS = 5
GAP_THRESHOLD_HOURS = 5


def _round_to_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


class SessionAnalyzer:
    """Groups UsageEntry items into 5-hour SessionBlocks."""

    def analyze(self, entries: list[UsageEntry]) -> list[SessionBlock]:
        if not entries:
            return []

        blocks: list[SessionBlock] = []
        sorted_entries = sorted(entries, key=lambda e: e.timestamp)

        current_start = _round_to_hour(sorted_entries[0].timestamp)
        current_end = current_start + timedelta(hours=SESSION_HOURS)
        current_entries: list[UsageEntry] = []
        block_idx = 0

        for entry in sorted_entries:
            # Entry falls outside current window
            if entry.timestamp >= current_end:
                # Save current block if it has entries
                if current_entries:
                    blocks.append(
                        SessionBlock(
                            id=f"block_{block_idx}",
                            start_time=current_start,
                            end_time=current_end,
                            entries=current_entries,
                        )
                    )
                    block_idx += 1

                # Check for gap
                gap = (entry.timestamp - current_end).total_seconds() / 3600
                if gap >= GAP_THRESHOLD_HOURS:
                    blocks.append(
                        SessionBlock(
                            id=f"gap_{block_idx}",
                            start_time=current_end,
                            end_time=_round_to_hour(entry.timestamp),
                            is_gap=True,
                        )
                    )
                    block_idx += 1

                # Start new window
                current_start = _round_to_hour(entry.timestamp)
                current_end = current_start + timedelta(hours=SESSION_HOURS)
                current_entries = []

            current_entries.append(entry)

        # Final block
        if current_entries:
            now = datetime.now(timezone.utc)
            is_active = now < current_end
            blocks.append(
                SessionBlock(
                    id=f"block_{block_idx}",
                    start_time=current_start,
                    end_time=current_end,
                    entries=current_entries,
                    is_active=is_active,
                )
            )

        return blocks

    def get_active_block(self, blocks: list[SessionBlock]) -> SessionBlock | None:
        for b in reversed(blocks):
            if b.is_active and not b.is_gap:
                return b
        return None

    def get_daily_stats(self, entries: list[UsageEntry]) -> list[dict]:
        """Aggregate entries by date."""
        by_date: dict[str, dict] = {}
        for e in entries:
            key = e.timestamp.strftime("%Y-%m-%d")
            if key not in by_date:
                by_date[key] = {
                    "date": key,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "messages": 0,
                    "models": set(),
                }
            d = by_date[key]
            d["input_tokens"] += e.input_tokens
            d["output_tokens"] += e.output_tokens
            d["cache_creation_tokens"] += e.cache_creation_tokens
            d["cache_read_tokens"] += e.cache_read_tokens
            d["total_tokens"] += e.total_tokens
            d["cost_usd"] += e.cost_usd
            d["messages"] += 1
            d["models"].add(e.model)

        result = []
        for d in sorted(by_date.values(), key=lambda x: x["date"], reverse=True):
            d["models"] = sorted(d["models"])
            result.append(d)
        return result

    def get_monthly_stats(self, entries: list[UsageEntry]) -> list[dict]:
        """Aggregate entries by month."""
        by_month: dict[str, dict] = {}
        for e in entries:
            key = e.timestamp.strftime("%Y-%m")
            if key not in by_month:
                by_month[key] = {
                    "month": key,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "messages": 0,
                    "models": set(),
                }
            d = by_month[key]
            d["input_tokens"] += e.input_tokens
            d["output_tokens"] += e.output_tokens
            d["total_tokens"] += e.total_tokens
            d["cost_usd"] += e.cost_usd
            d["messages"] += 1
            d["models"].add(e.model)

        result = []
        for d in sorted(by_month.values(), key=lambda x: x["month"], reverse=True):
            d["models"] = sorted(d["models"])
            result.append(d)
        return result
