"""Analysis engine — computes burn rate, P90 limits, pace, projections, sparklines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import quantiles

from claude_monitor_tool.models import (
    ApiQuota,
    BurnRate,
    MonitorState,
    PlanLimits,
    SessionBlock,
    UsageEntry,
)


class AnalysisEngine:
    """Stateless analysis functions that compute metrics from raw data."""

    def build_state(
        self,
        entries: list[UsageEntry],
        blocks: list[SessionBlock],
        active_block: SessionBlock | None,
        plan: PlanLimits,
        api_quota: ApiQuota | None = None,
    ) -> MonitorState:
        """Build a complete MonitorState from raw data."""
        state = MonitorState(plan=plan, api_quota=api_quota)

        if active_block:
            state.active_block = active_block
            state.total_tokens = active_block.tokens.total
            state.total_cost = active_block.cost_usd
            state.total_messages = active_block.message_count
            state.burn_rate = active_block.burn_rate
            state.model_breakdown = active_block.models_used

            # Projections
            state.tokens_exhaust_time = self._project_exhaust_time(active_block, plan)
            state.session_reset_time = active_block.end_time

        state.recent_blocks = [b for b in blocks if not b.is_gap][-10:]
        state.sparkline_data = self._build_sparkline(entries)
        state.p90_limit = self._calculate_p90(blocks)
        state.last_updated = datetime.now(timezone.utc)

        return state

    def _project_exhaust_time(
        self, block: SessionBlock, plan: PlanLimits
    ) -> datetime | None:
        """Predict when tokens will run out at current burn rate."""
        rate = block.burn_rate
        if rate.tokens_per_minute <= 0:
            return None

        remaining = plan.token_limit - block.tokens.total
        if remaining <= 0:
            return datetime.now(timezone.utc)

        minutes_left = remaining / rate.tokens_per_minute
        return datetime.now(timezone.utc) + timedelta(minutes=minutes_left)

    def _build_sparkline(self, entries: list[UsageEntry]) -> list[float]:
        """Build hourly token counts for the last 12 hours."""
        if not entries:
            return []

        now = datetime.now(timezone.utc)
        buckets: list[float] = [0.0] * 12

        for e in entries:
            hours_ago = (now - e.timestamp).total_seconds() / 3600
            if 0 <= hours_ago < 12:
                idx = 11 - int(hours_ago)
                buckets[idx] += e.total_tokens

        return buckets

    def _calculate_p90(self, blocks: list[SessionBlock]) -> int | None:
        """Calculate 90th percentile token usage from completed sessions."""
        completed = [b for b in blocks if not b.is_active and not b.is_gap and b.entries]
        if len(completed) < 3:
            return None

        totals = sorted(b.tokens.total for b in completed)
        try:
            deciles = quantiles(totals, n=10)
            return int(deciles[8]) if len(deciles) > 8 else int(totals[-1])
        except Exception:
            return int(totals[-1]) if totals else None

    @staticmethod
    def pace_indicator(api_quota: ApiQuota | None) -> str:
        """Calculate pace vs expected consumption (from Repo 2 pattern)."""
        if not api_quota:
            return ""

        used = api_quota.five_hour_used_pct
        reset_min = api_quota.five_hour_reset_minutes
        total_min = 5 * 60

        if reset_min <= 0 or total_min <= 0:
            return ""

        elapsed_min = total_min - reset_min
        if elapsed_min <= 0:
            return ""

        expected_pct = (elapsed_min / total_min) * 100
        delta = used - expected_pct

        if abs(delta) < 10:
            return "on track"
        elif delta > 0:
            return f"+{delta:.0f}% ahead"
        else:
            return f"{delta:.0f}% under"

    @staticmethod
    def format_sparkline(data: list[float]) -> str:
        """Render sparkline from data points using Unicode block characters."""
        if not data:
            return ""

        blocks = " ▁▂▃▄▅▆▇█"
        mx = max(data) if max(data) > 0 else 1
        return "".join(blocks[min(8, int(v / mx * 8))] for v in data)
