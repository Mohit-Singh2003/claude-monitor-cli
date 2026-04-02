"""View screens -- Realtime dashboard, Daily table, Monthly table, Sessions list."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Label, Static

from claude_monitor_tool.models import MonitorState
from claude_monitor_tool.tui.theme import (
    GREEN,
    PURPLE,
    PURPLE_DIM,
    RED,
    TEXT_MUTED,
    TEXT_SECONDARY,
    YELLOW,
    bar_color,
)
from claude_monitor_tool.tui.widgets import (
    MetricLine,
    ModelBar,
    ProgressRow,
    QuotaGauge,
    SparklineWidget,
)

logger = logging.getLogger(__name__)


class SectionHeader(Static):
    """Thin colored section label."""

    DEFAULT_CSS = f"""
    SectionHeader {{
        height: 1;
        color: {PURPLE};
        text-style: bold;
        margin: 0;
        padding: 0;
    }}
    """

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self._text = text

    def render(self) -> str:
        return f"[{PURPLE}]--- {self._text} ---[/]"


class RealtimeView(VerticalScroll):
    """Main real-time dashboard view."""

    can_focus = True

    DEFAULT_CSS = """
    RealtimeView {
        height: 1fr;
        padding: 0 2;
        scrollbar-size: 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield SectionHeader("Quotas")
        yield QuotaGauge(label="5h Quota", id="quota-5h")
        yield QuotaGauge(label="7d Quota", id="quota-7d")

        yield SectionHeader("Usage")
        yield ProgressRow(label="Tokens", id="prog-tokens")
        yield ProgressRow(label="Cost", prefix="$", id="prog-cost")
        yield ProgressRow(label="Messages", id="prog-messages")

        yield SectionHeader("Analytics")
        yield MetricLine(label="Burn Rate", id="metric-burn")
        yield MetricLine(label="Cost Rate", id="metric-cost-rate")
        yield MetricLine(label="Pace", id="metric-pace")
        yield SparklineWidget(label="Trend", id="sparkline")
        yield ModelBar(id="model-bar")

        yield SectionHeader("Projections")
        yield MetricLine(label="Token Exhaust", id="metric-exhaust")
        yield MetricLine(label="Session Reset", id="metric-reset")

    def update_state(self, state: MonitorState) -> None:
        """Push new MonitorState into all child widgets."""
        plan = state.plan

        # Quotas
        q5h = self.query_one("#quota-5h", QuotaGauge)
        q7d = self.query_one("#quota-7d", QuotaGauge)
        if state.api_quota:
            q5h.update_values(state.api_quota.five_hour_used_pct, state.api_quota.five_hour_reset_minutes)
            q7d.update_values(state.api_quota.seven_day_used_pct, state.api_quota.seven_day_reset_minutes)
        else:
            q5h.update_values(0, 0)
            q7d.update_values(0, 0)

        # Progress bars
        self.query_one("#prog-tokens", ProgressRow).update_values(state.total_tokens, plan.token_limit)
        self.query_one("#prog-cost", ProgressRow).update_values(state.total_cost, plan.cost_limit)
        self.query_one("#prog-messages", ProgressRow).update_values(state.total_messages, plan.message_limit)

        # Analytics
        br = state.burn_rate
        burn_color = GREEN if br.tokens_per_minute < 100 else (YELLOW if br.tokens_per_minute < 250 else RED)
        self.query_one("#metric-burn", MetricLine).set_value(
            f"[{burn_color}]{br.tokens_per_minute:.1f} tok/min[/]"
        )
        self.query_one("#metric-cost-rate", MetricLine).set_value(
            f"${br.cost_per_hour / 60:.4f}/min"
        )

        from claude_monitor_tool.analysis.engine import AnalysisEngine
        pace = AnalysisEngine.pace_indicator(state.api_quota)
        pace_color = GREEN if "under" in pace or "on track" in pace else (RED if "ahead" in pace else TEXT_MUTED)
        self.query_one("#metric-pace", MetricLine).set_value(
            f"[{pace_color}]{pace or '--'}[/]"
        )

        self.query_one("#sparkline", SparklineWidget).update_data(state.sparkline_data)
        self.query_one("#model-bar", ModelBar).update_breakdown(state.model_breakdown)

        # Projections
        if state.tokens_exhaust_time:
            t = state.tokens_exhaust_time.strftime("%I:%M %p")
            delta = (state.tokens_exhaust_time - state.last_updated).total_seconds() / 60
            if delta > 0:
                h, m = int(delta // 60), int(delta % 60)
                self.query_one("#metric-exhaust", MetricLine).set_value(f"~{t} (in {h}h {m:02d}m)")
            else:
                self.query_one("#metric-exhaust", MetricLine).set_value(f"[{RED}]exceeded[/]")
        else:
            self.query_one("#metric-exhaust", MetricLine).set_value(f"[{TEXT_MUTED}]--[/]")

        if state.session_reset_time:
            t = state.session_reset_time.strftime("%I:%M %p")
            self.query_one("#metric-reset", MetricLine).set_value(t)
        else:
            self.query_one("#metric-reset", MetricLine).set_value(f"[{TEXT_MUTED}]--[/]")


class DailyView(VerticalScroll):
    """Daily aggregated usage table."""

    can_focus = True

    DEFAULT_CSS = """
    DailyView {
        height: 1fr;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield SectionHeader("Daily Usage")
        table = DataTable(id="daily-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#daily-table", DataTable)
        table.add_columns("Date", "Models", "Input", "Output", "Total", "Cost", "Msgs")

    def update_state(self, state: MonitorState) -> None:
        table = self.query_one("#daily-table", DataTable)
        table.clear()
        for d in state.daily_stats[:30]:
            models = ", ".join(d.get("models", []))
            table.add_row(
                d["date"],
                models,
                f"{d['input_tokens']:,}",
                f"{d['output_tokens']:,}",
                f"{d['total_tokens']:,}",
                f"${d['cost_usd']:.2f}",
                str(d["messages"]),
            )


class MonthlyView(VerticalScroll):
    """Monthly aggregated usage table."""

    can_focus = True

    DEFAULT_CSS = """
    MonthlyView {
        height: 1fr;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield SectionHeader("Monthly Usage")
        table = DataTable(id="monthly-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#monthly-table", DataTable)
        table.add_columns("Month", "Models", "Input", "Output", "Total", "Cost", "Msgs")

    def update_state(self, state: MonitorState) -> None:
        table = self.query_one("#monthly-table", DataTable)
        table.clear()
        for d in state.monthly_stats[:12]:
            models = ", ".join(d.get("models", []))
            table.add_row(
                d["month"],
                models,
                f"{d['input_tokens']:,}",
                f"{d['output_tokens']:,}",
                f"{d['total_tokens']:,}",
                f"${d['cost_usd']:.2f}",
                str(d["messages"]),
            )


class SessionsView(VerticalScroll):
    """Session history list."""

    can_focus = True

    DEFAULT_CSS = """
    SessionsView {
        height: 1fr;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield SectionHeader("Session History")
        table = DataTable(id="sessions-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.add_columns("Session", "Start", "End", "Duration", "Tokens", "Cost", "Models", "Status")

    def update_state(self, state: MonitorState) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.clear()
        for b in reversed(state.recent_blocks):
            dur = b.duration_minutes
            h, m = int(dur // 60), int(dur % 60)
            models = ", ".join(b.models_used.keys())
            status = "active" if b.is_active else "ended"
            table.add_row(
                b.id,
                b.start_time.strftime("%m/%d %H:%M"),
                b.actual_end_time.strftime("%H:%M"),
                f"{h}h {m:02d}m",
                f"{b.tokens.total:,}",
                f"${b.cost_usd:.2f}",
                models,
                status,
            )
