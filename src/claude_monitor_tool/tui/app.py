"""Main Textual application — Claude Monitor TUI."""

from __future__ import annotations

import logging
from functools import partial

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Label, Static, TabbedContent, TabPane
from textual.worker import Worker, get_current_worker

from claude_monitor_tool.models import MonitorState, Plan, PlanLimits
from claude_monitor_tool.tui.theme import PURPLE, TEXT_MUTED, TEXT_SECONDARY, THEME_CSS
from claude_monitor_tool.tui.views import DailyView, MonthlyView, RealtimeView, SessionsView

logger = logging.getLogger(__name__)


class HeaderBar(Static):
    """Custom header showing model + project info."""

    DEFAULT_CSS = """
    HeaderBar {
        dock: top;
        height: 1;
        background: #1E293B;
        color: #A78BFA;
        text-style: bold;
        content-align: center middle;
        width: 100%;
    }
    """

    def __init__(self, plan: str = "pro", **kwargs):
        super().__init__(**kwargs)
        self._plan = plan
        self._model = ""
        self._project = ""

    def set_info(self, model: str = "", project: str = "", plan: str = ""):
        self._model = model
        self._project = project
        if plan:
            self._plan = plan
        self.refresh()

    def render(self) -> str:
        from claude_monitor_tool import __version__

        left = ""
        if self._model:
            left = f"[bold]\u25c6 {self._model}[/]"
            if self._project:
                left += f"  [{TEXT_MUTED}]|[/]  [{TEXT_SECONDARY}]{self._project}[/]"

        right = f"[{TEXT_MUTED}]{self._plan} \u00b7 v{__version__}[/]"

        if left:
            return f"  {left}{'':>10}{right}  "
        return f"  [{PURPLE}]Claude Monitor[/]{'':>10}{right}  "


def _load_data_sync(plan: Plan) -> MonitorState | None:
    """Load data synchronously — runs in a worker thread."""
    try:
        from claude_monitor_tool.data.reader import JsonlReader
        from claude_monitor_tool.data.api_client import ApiClient
        from claude_monitor_tool.data.session_analyzer import SessionAnalyzer
        from claude_monitor_tool.analysis.engine import AnalysisEngine

        reader = JsonlReader()
        api = ApiClient()
        analyzer = SessionAnalyzer()
        engine = AnalysisEngine()

        entries = reader.read_entries(hours=192)
        blocks = analyzer.analyze(entries)
        active = analyzer.get_active_block(blocks)
        quota = api.get_quota() if api.available else None

        plan_limits = PlanLimits.for_plan(plan)

        state = engine.build_state(
            entries=entries,
            blocks=blocks,
            active_block=active,
            plan=plan_limits,
            api_quota=quota,
        )

        state.daily_stats = analyzer.get_daily_stats(entries)
        state.monthly_stats = analyzer.get_monthly_stats(entries)

        if active and active.entries:
            state.current_model = active.entries[-1].model

        return state
    except Exception as exc:
        logger.error("Data load failed: %s", exc, exc_info=True)
        return None


class ClaudeMonitorApp(App):
    """Interactive Claude AI usage monitor."""

    TITLE = "Claude Monitor"
    CSS = THEME_CSS

    BINDINGS = [
        Binding("r", "switch_tab('realtime')", "Realtime", show=True),
        Binding("d", "switch_tab('daily')", "Daily", show=True),
        Binding("m", "switch_tab('monthly')", "Monthly", show=True),
        Binding("s", "switch_tab('sessions')", "Sessions", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("f5", "refresh_data", "Refresh", show=True),
    ]

    def __init__(self, plan: Plan = Plan.PRO, **kwargs):
        super().__init__(**kwargs)
        self._plan = plan
        self._state: MonitorState | None = None
        self._refresh_interval = 10

    def compose(self) -> ComposeResult:
        yield HeaderBar(plan=self._plan.value, id="header-bar")
        with TabbedContent(initial="realtime"):
            with TabPane("Realtime", id="realtime"):
                yield RealtimeView(id="realtime-view")
            with TabPane("Daily", id="daily"):
                yield DailyView(id="daily-view")
            with TabPane("Monthly", id="monthly"):
                yield MonthlyView(id="monthly-view")
            with TabPane("Sessions", id="sessions"):
                yield SessionsView(id="sessions-view")
        yield Footer()

    def on_mount(self) -> None:
        """Start the data refresh timer."""
        self._do_refresh()
        self.set_interval(self._refresh_interval, self._do_refresh)

    def _do_refresh(self) -> None:
        """Kick off a background worker to load data."""
        self.run_worker(
            partial(_load_data_sync, self._plan),
            thread=True,
            name="data-loader",
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion — push state to UI."""
        if event.worker.name != "data-loader":
            return
        if event.worker.is_finished and event.worker.result is not None:
            state = event.worker.result
            self._state = state
            self._push_state(state)

    def _push_state(self, state: MonitorState) -> None:
        """Push state to all views."""
        try:
            self.query_one("#header-bar", HeaderBar).set_info(
                model=state.current_model,
                project=state.project_name or state.git_branch,
                plan=state.plan.name.value,
            )
        except Exception as exc:
            logger.debug("Header update failed: %s", exc)

        try:
            self.query_one("#realtime-view", RealtimeView).update_state(state)
        except Exception as exc:
            logger.debug("Realtime view update failed: %s", exc)

        try:
            self.query_one("#daily-view", DailyView).update_state(state)
        except Exception as exc:
            logger.debug("Daily view update failed: %s", exc)

        try:
            self.query_one("#monthly-view", MonthlyView).update_state(state)
        except Exception as exc:
            logger.debug("Monthly view update failed: %s", exc)

        try:
            self.query_one("#sessions-view", SessionsView).update_state(state)
        except Exception as exc:
            logger.debug("Sessions view update failed: %s", exc)

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab."""
        tabbed = self.query_one(TabbedContent)
        tabbed.active = tab_id

    def action_refresh_data(self) -> None:
        """Force a data refresh."""
        self._do_refresh()
