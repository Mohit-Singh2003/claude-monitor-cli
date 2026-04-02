"""OAuth API client — fetches real quota data from Anthropic's usage endpoint.

SECURITY NOTES:
- The OAuth token is read from ~/.claude/.credentials.json (Claude Code's own credential store)
- It is ONLY sent to https://api.anthropic.com (the token's own issuer)
- The token is NEVER written to cache, logs, or any other file
- The cache file stores only the API *response* (utilization percentages, reset times)
- The token is short-lived (~12h) and auto-refreshed by Claude Code
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from claude_monitor_tool.models import ApiQuota

logger = logging.getLogger(__name__)

_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_BETA_HEADER = "oauth-2025-04-20"
_CACHE_TTL = 300  # 5 minutes
_CACHE_FILE = Path(tempfile.gettempdir()) / "claude-monitor-usage.json"
_LOCK_FILE = Path(tempfile.gettempdir()) / "claude-monitor-usage.lock"


def _get_oauth_token() -> str | None:
    """Find OAuth token from env or credentials file."""
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        return token

    cred_path = Path.home() / ".claude" / ".credentials.json"
    if cred_path.exists():
        try:
            data = json.loads(cred_path.read_text(encoding="utf-8"))
            return data.get("claudeAiOauth", {}).get("accessToken")
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def _read_cache() -> dict | None:
    """Read cached quota data if fresh."""
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if time.time() - data.get("_ts", 0) < _CACHE_TTL:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _write_cache(data: dict) -> None:
    """Write quota data to cache. NEVER contains the OAuth token — only API response data."""
    data["_ts"] = time.time()
    try:
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
        # Restrict permissions to owner-only on Unix
        if os.name != "nt":
            os.chmod(_CACHE_FILE, 0o600)
    except OSError:
        pass


def _acquire_lock() -> bool:
    """Non-blocking lock file acquisition."""
    try:
        if _LOCK_FILE.exists():
            age = time.time() - _LOCK_FILE.stat().st_mtime
            if age < 30:
                return False
        _LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError:
        return False


def _release_lock() -> None:
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _fetch_usage(token: str) -> dict | None:
    """Make HTTPS request to Anthropic usage API."""
    req = Request(
        _USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": _BETA_HEADER,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("API fetch failed: %s", exc)
        return None


def _parse_reset_minutes(iso_str: str | None) -> float:
    """Parse ISO8601 reset timestamp into minutes from now."""
    if not iso_str:
        return 0.0
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        now = datetime.now(timezone.utc)
        return max(0.0, (dt - now).total_seconds() / 60.0)
    except (ValueError, TypeError):
        return 0.0


class ApiClient:
    """Fetches real-time quota data from Anthropic's OAuth usage endpoint."""

    def __init__(self):
        self._token = _get_oauth_token()
        self._last_quota: ApiQuota | None = None
        self._bg_thread: threading.Thread | None = None

    @property
    def available(self) -> bool:
        return self._token is not None

    def get_quota(self) -> ApiQuota | None:
        """Get quota data — returns cached if fresh, triggers background fetch if stale."""
        cached = _read_cache()
        if cached:
            self._last_quota = self._parse_quota(cached)
            return self._last_quota

        # Trigger background fetch
        if self._token and (self._bg_thread is None or not self._bg_thread.is_alive()):
            self._bg_thread = threading.Thread(target=self._bg_fetch, daemon=True)
            self._bg_thread.start()

        return self._last_quota

    def _bg_fetch(self) -> None:
        """Background thread: fetch and cache."""
        if not _acquire_lock():
            return
        try:
            if not self._token:
                return
            data = _fetch_usage(self._token)
            if data:
                _write_cache(data)
                self._last_quota = self._parse_quota(data)
        finally:
            _release_lock()

    @staticmethod
    def _parse_quota(data: dict) -> ApiQuota:
        """Parse raw API response into ApiQuota.

        Actual API response format (2025):
          {"five_hour": {"utilization": 76.0, "resets_at": "..."}, ...}
        """
        five_h = data.get("five_hour", {}) or {}
        seven_d = data.get("seven_day", {}) or {}
        extra = data.get("extra_usage", {}) or {}

        return ApiQuota(
            five_hour_used_pct=float(five_h.get("utilization", 0) or 0),
            five_hour_reset_minutes=_parse_reset_minutes(five_h.get("resets_at")),
            seven_day_used_pct=float(seven_d.get("utilization", 0) or 0),
            seven_day_reset_minutes=_parse_reset_minutes(seven_d.get("resets_at")),
            has_extra_credits=bool(extra.get("is_enabled", False)),
        )
