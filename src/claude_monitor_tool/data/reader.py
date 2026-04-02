"""JSONL file reader — loads Claude Code usage data from local config files."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from claude_monitor_tool.models import UsageEntry

logger = logging.getLogger(__name__)

# Standard Claude config locations
_CONFIG_DIRS = [
    Path.home() / ".claude" / "projects",
    Path.home() / ".config" / "claude" / "projects",
]


def _find_config_dir() -> Path | None:
    """Find the Claude projects directory."""
    import os

    env_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_dir:
        p = Path(env_dir) / "projects"
        if p.exists():
            return p

    for d in _CONFIG_DIRS:
        if d.exists():
            return d
    return None


def _parse_timestamp(raw: str | float | int) -> datetime:
    """Parse various timestamp formats into UTC datetime."""
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)

    raw = raw.strip()
    # Handle Z suffix
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass

    # Fallback: strip fractional seconds
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return datetime.now(timezone.utc)


def _extract_tokens(data: dict) -> dict[str, int]:
    """Extract token counts from a usage/message dict, handling both camelCase and snake_case."""
    result = {"input_tokens": 0, "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}

    usage = data.get("usage") or data.get("message", {}).get("usage", {})
    if not usage:
        return result

    for snake, camel in [
        ("input_tokens", "inputTokens"),
        ("output_tokens", "outputTokens"),
        ("cache_creation_tokens", "cacheCreationTokens"),
        ("cache_read_tokens", "cacheReadTokens"),
    ]:
        result[snake] = int(usage.get(snake, 0) or usage.get(camel, 0) or 0)

    return result


def _extract_model(data: dict) -> str:
    """Extract model name from entry."""
    model = data.get("model", "")
    if not model:
        msg = data.get("message", {})
        model = msg.get("model", "") or msg.get("display_name", "")
    return _normalize_model(model) if model else "unknown"


def _normalize_model(name: str) -> str:
    """Normalize model name to short form."""
    name_lower = name.lower()
    if "opus" in name_lower:
        return "opus"
    if "sonnet" in name_lower:
        return "sonnet"
    if "haiku" in name_lower:
        return "haiku"
    return name.split("/")[-1] if "/" in name else name


class JsonlReader:
    """Reads and parses Claude Code JSONL usage files."""

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or _find_config_dir()

    @property
    def available(self) -> bool:
        return self._config_dir is not None and self._config_dir.exists()

    def read_entries(self, hours: int = 192) -> list[UsageEntry]:
        """Read all usage entries from the last N hours."""
        if not self.available:
            return []

        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        entries: list[UsageEntry] = []
        seen: set[str] = set()

        for jsonl_file in self._config_dir.rglob("*.jsonl"):
            try:
                entries.extend(self._read_file(jsonl_file, cutoff, seen))
            except Exception as exc:
                logger.debug("Skipping %s: %s", jsonl_file, exc)

        entries.sort(key=lambda e: e.timestamp)
        return entries

    def _read_file(
        self, path: Path, cutoff: float, seen: set[str]
    ) -> list[UsageEntry]:
        results: list[UsageEntry] = []

        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Skip non-assistant entries (they don't carry usage)
                entry_type = data.get("type", "")
                if entry_type not in ("assistant", ""):
                    continue

                tokens = _extract_tokens(data)
                if tokens["input_tokens"] == 0 and tokens["output_tokens"] == 0:
                    continue

                # Parse timestamp
                raw_ts = data.get("timestamp") or data.get("createdAt") or data.get("created_at")
                if not raw_ts:
                    continue

                ts = _parse_timestamp(raw_ts)
                if ts.timestamp() < cutoff:
                    continue

                # Dedup
                msg_id = data.get("message_id") or data.get("messageId", "")
                req_id = data.get("request_id") or data.get("requestId", "")
                dedup = f"{msg_id}:{req_id}"
                if dedup != ":" and dedup in seen:
                    continue
                if dedup != ":":
                    seen.add(dedup)

                # Cost
                cost = float(data.get("cost", 0) or data.get("costUSD", 0) or 0)
                if cost == 0:
                    cost = _estimate_cost(tokens, _extract_model(data))

                results.append(
                    UsageEntry(
                        timestamp=ts,
                        input_tokens=tokens["input_tokens"],
                        output_tokens=tokens["output_tokens"],
                        cache_creation_tokens=tokens["cache_creation_tokens"],
                        cache_read_tokens=tokens["cache_read_tokens"],
                        cost_usd=cost,
                        model=_extract_model(data),
                        message_id=msg_id,
                        request_id=req_id,
                    )
                )

        return results


# Pricing per million tokens
_PRICING: dict[str, dict[str, float]] = {
    "opus": {"input": 15.0, "output": 75.0, "cache_creation": 18.75, "cache_read": 1.50},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_creation": 3.75, "cache_read": 0.30},
    "haiku": {"input": 0.25, "output": 1.25, "cache_creation": 0.30, "cache_read": 0.03},
}


def _estimate_cost(tokens: dict[str, int], model: str) -> float:
    pricing = _PRICING.get(model, _PRICING["sonnet"])
    cost = 0.0
    cost += (tokens["input_tokens"] / 1_000_000) * pricing["input"]
    cost += (tokens["output_tokens"] / 1_000_000) * pricing["output"]
    cost += (tokens["cache_creation_tokens"] / 1_000_000) * pricing["cache_creation"]
    cost += (tokens["cache_read_tokens"] / 1_000_000) * pricing["cache_read"]
    return cost
