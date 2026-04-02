"""Core data models shared across all layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Plan(str, Enum):
    PRO = "pro"
    MAX5 = "max5"
    MAX20 = "max20"
    CUSTOM = "custom"


@dataclass
class PlanLimits:
    name: Plan
    token_limit: int
    cost_limit: float
    message_limit: int

    @staticmethod
    def for_plan(plan: Plan) -> PlanLimits:
        return _PLAN_DEFAULTS[plan]


_PLAN_DEFAULTS: dict[Plan, PlanLimits] = {
    Plan.PRO: PlanLimits(Plan.PRO, token_limit=19_000, cost_limit=18.0, message_limit=250),
    Plan.MAX5: PlanLimits(Plan.MAX5, token_limit=88_000, cost_limit=35.0, message_limit=1_000),
    Plan.MAX20: PlanLimits(Plan.MAX20, token_limit=220_000, cost_limit=140.0, message_limit=2_000),
    Plan.CUSTOM: PlanLimits(Plan.CUSTOM, token_limit=44_000, cost_limit=50.0, message_limit=500),
}


@dataclass
class TokenCounts:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )


@dataclass
class BurnRate:
    tokens_per_minute: float = 0.0
    cost_per_hour: float = 0.0


@dataclass
class UsageEntry:
    timestamp: datetime
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    model: str = "unknown"
    message_id: str = ""
    request_id: str = ""

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    @property
    def dedup_key(self) -> str:
        return f"{self.message_id}:{self.request_id}"


@dataclass
class SessionBlock:
    id: str
    start_time: datetime
    end_time: datetime
    entries: list[UsageEntry] = field(default_factory=list)
    is_active: bool = False
    is_gap: bool = False

    @property
    def tokens(self) -> TokenCounts:
        tc = TokenCounts()
        for e in self.entries:
            tc.input_tokens += e.input_tokens
            tc.output_tokens += e.output_tokens
            tc.cache_creation_tokens += e.cache_creation_tokens
            tc.cache_read_tokens += e.cache_read_tokens
        return tc

    @property
    def cost_usd(self) -> float:
        return sum(e.cost_usd for e in self.entries)

    @property
    def message_count(self) -> int:
        return len(self.entries)

    @property
    def duration_minutes(self) -> float:
        if not self.entries:
            return 0.0
        first = self.entries[0].timestamp
        last = self.entries[-1].timestamp
        return max((last - first).total_seconds() / 60.0, 0.1)

    @property
    def burn_rate(self) -> BurnRate:
        if not self.entries or self.is_gap:
            return BurnRate()
        mins = self.duration_minutes
        return BurnRate(
            tokens_per_minute=self.tokens.total / mins,
            cost_per_hour=(self.cost_usd / mins) * 60.0,
        )

    @property
    def models_used(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.model] = counts.get(e.model, 0) + e.total_tokens
        return counts

    @property
    def actual_end_time(self) -> datetime:
        if self.entries:
            return self.entries[-1].timestamp
        return self.end_time


@dataclass
class ApiQuota:
    """Real quota data from Anthropic's OAuth usage API."""

    five_hour_used_pct: float = 0.0
    five_hour_reset_minutes: float = 0.0
    seven_day_used_pct: float = 0.0
    seven_day_reset_minutes: float = 0.0
    has_extra_credits: bool = False
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def five_hour_remaining_pct(self) -> float:
        return max(0.0, 100.0 - self.five_hour_used_pct)

    @property
    def seven_day_remaining_pct(self) -> float:
        return max(0.0, 100.0 - self.seven_day_used_pct)


@dataclass
class MonitorState:
    """Aggregated state passed to the TUI for rendering."""

    plan: PlanLimits = field(default_factory=lambda: PlanLimits.for_plan(Plan.PRO))
    active_block: SessionBlock | None = None
    recent_blocks: list[SessionBlock] = field(default_factory=list)
    api_quota: ApiQuota | None = None
    current_model: str = ""
    project_name: str = ""
    git_branch: str = ""
    error: str | None = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Aggregated metrics
    total_tokens: int = 0
    total_cost: float = 0.0
    total_messages: int = 0
    burn_rate: BurnRate = field(default_factory=BurnRate)
    p90_limit: int | None = None

    # Projections
    tokens_exhaust_time: datetime | None = None
    session_reset_time: datetime | None = None

    # Sparkline data (hourly token counts for last 12 hours)
    sparkline_data: list[float] = field(default_factory=list)

    # Per-model breakdown
    model_breakdown: dict[str, int] = field(default_factory=dict)

    # Daily aggregates for table views
    daily_stats: list[dict] = field(default_factory=list)
    monthly_stats: list[dict] = field(default_factory=list)
