"""Custom Textual widgets -- gauges, progress bars, sparklines, metric rows."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from claude_monitor_tool.tui.theme import (
    BAR_EMPTY,
    PURPLE,
    TEXT_MUTED,
    TEXT_SECONDARY,
    bar_color,
    model_color,
)


class GaugeBar(Static):
    """Compact 5-block gauge (from Repo 2 pattern)."""

    DEFAULT_CSS = "GaugeBar { height: 1; }"

    value: reactive[float] = reactive(0.0)

    FILLED = "\u25b0"  # filled block
    EMPTY = "\u25b1"   # empty block
    BLOCKS = 5

    def __init__(self, value: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    def render(self) -> str:
        filled = round(min(100, max(0, self.value)) / 100 * self.BLOCKS)
        color = bar_color(self.value)
        filled_str = self.FILLED * filled
        empty_str = self.EMPTY * (self.BLOCKS - filled)
        return f"[{color}]{filled_str}[/][{BAR_EMPTY}]{empty_str}[/]"


class ProgressRow(Static):
    """Full-width progress bar row: Label [bar] 62%  27,280 / 44,000"""

    DEFAULT_CSS = "ProgressRow { height: 1; width: 100%; }"

    def __init__(
        self,
        label: str = "",
        current: float = 0,
        maximum: float = 100,
        unit: str = "",
        prefix: str = "",
        bar_width: int = 30,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._label = label
        self._current = current
        self._maximum = maximum
        self._unit = unit
        self._prefix = prefix
        self._bar_width = bar_width

    def update_values(self, current: float, maximum: float, label: str | None = None):
        self._current = current
        self._maximum = maximum
        if label is not None:
            self._label = label
        self.refresh()

    def render(self) -> str:
        pct = (self._current / self._maximum * 100) if self._maximum > 0 else 0
        pct = min(100, max(0, pct))
        color = bar_color(pct)

        filled = int(pct / 100 * self._bar_width)
        empty = self._bar_width - filled
        bar_filled = "\u2588" * filled   # full block
        bar_empty = "\u2591" * empty     # light shade
        bar = f"[{color}]{bar_filled}[/][{BAR_EMPTY}]{bar_empty}[/]"

        if self._prefix:
            cur = f"{self._prefix}{self._current:,.2f}"
            mx = f"{self._prefix}{self._maximum:,.2f}"
        elif self._maximum >= 1000:
            cur = f"{self._current:,.0f}"
            mx = f"{self._maximum:,.0f}"
        else:
            cur = f"{self._current:.1f}"
            mx = f"{self._maximum:.1f}"

        return (
            f"[{TEXT_SECONDARY}]{self._label:<14}[/]"
            f"{bar} "
            f"[bold]{pct:>5.1f}%[/]  "
            f"[{TEXT_SECONDARY}]{cur} / {mx}[/]"
            f"{'  ' + self._unit if self._unit else ''}"
        )


class MetricLine(Static):
    """Simple key-value metric line: Burn Rate   142.3 tok/min"""

    DEFAULT_CSS = "MetricLine { height: 1; width: 100%; }"

    def __init__(self, label: str = "", value: str = "", **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._value = value or "--"

    def set_value(self, value: str, label: str | None = None):
        self._value = value
        if label is not None:
            self._label = label
        self.refresh()

    def render(self) -> str:
        return f"[{TEXT_SECONDARY}]{self._label:<18}[/][bold]{self._value}[/]"


class ModelBar(Static):
    """Model distribution bar: sonnet [gauge] 78%  opus [gauge] 22%"""

    DEFAULT_CSS = "ModelBar { height: 1; width: 100%; }"

    def __init__(self, breakdown: dict[str, int] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._breakdown = breakdown or {}

    def update_breakdown(self, breakdown: dict[str, int]):
        self._breakdown = breakdown
        self.refresh()

    def render(self) -> str:
        if not self._breakdown:
            return f"[{TEXT_MUTED}]Models            --[/]"

        total = sum(self._breakdown.values())
        if total == 0:
            return f"[{TEXT_MUTED}]Models            --[/]"

        parts = []
        for model_name, tokens in sorted(self._breakdown.items(), key=lambda x: -x[1]):
            pct = tokens / total * 100
            color = model_color(model_name)
            filled = round(pct / 100 * 5)
            gauge = "\u25b0" * filled + "\u25b1" * (5 - filled)
            parts.append(f"[{color}]{model_name}[/] [{color}]{gauge}[/] {pct:.0f}%")

        return f"[{TEXT_SECONDARY}]Models          [/]" + "    ".join(parts)


class SparklineWidget(Static):
    """Inline sparkline chart."""

    DEFAULT_CSS = "SparklineWidget { height: 1; width: 100%; }"

    BLOCKS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

    def __init__(self, data: list[float] | None = None, label: str = "", **kwargs):
        super().__init__(**kwargs)
        self._data = data or []
        self._label = label

    def update_data(self, data: list[float]):
        self._data = data
        self.refresh()

    def render(self) -> str:
        if not self._data or max(self._data) == 0:
            return f"[{TEXT_SECONDARY}]{self._label:<18}[/][{TEXT_MUTED}]--[/]"

        mx = max(self._data)
        chars = "".join(
            self.BLOCKS[min(8, int(v / mx * 8))] for v in self._data
        )

        return (
            f"[{TEXT_SECONDARY}]{self._label:<18}[/]"
            f"[{PURPLE}]{chars}[/]"
            f"  [{TEXT_MUTED}](12h)[/]"
        )


class QuotaGauge(Static):
    """Quota line with gauge: 5h Quota  [gauge]  62% remaining  resets in 2h 12m"""

    DEFAULT_CSS = "QuotaGauge { height: 1; width: 100%; }"

    def __init__(
        self,
        label: str = "",
        used_pct: float = 0,
        reset_minutes: float = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._label = label
        self._used_pct = used_pct
        self._reset_minutes = reset_minutes

    def update_values(self, used_pct: float, reset_minutes: float):
        self._used_pct = used_pct
        self._reset_minutes = reset_minutes
        self.refresh()

    def render(self) -> str:
        remaining = max(0, 100 - self._used_pct)
        color = bar_color(self._used_pct)
        filled = round(min(100, max(0, self._used_pct)) / 100 * 5)
        gauge = "\u25b0" * filled + "\u25b1" * (5 - filled)

        reset_str = ""
        if self._reset_minutes > 0:
            h = int(self._reset_minutes // 60)
            m = int(self._reset_minutes % 60)
            reset_str = f"  [{TEXT_MUTED}]resets in {h}h {m:02d}m[/]"

        return (
            f"[{TEXT_SECONDARY}]{self._label:<14}[/]"
            f"[{color}]{gauge}[/]  "
            f"[bold]{remaining:.0f}% remaining[/]"
            f"{reset_str}"
        )
