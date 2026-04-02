# Security Policy

## How This Tool Accesses Your Data

Claude Monitor Tool reads usage data from two sources on your local machine. It does **not** require an API key, does **not** collect telemetry, and does **not** send your data to any third party.

### 1. Local JSONL Files (offline)

Claude Code logs session data to `~/.claude/projects/` as JSONL files. This tool reads those files to compute token counts, cost estimates, session history, and burn rate analytics.

- **Read-only** — files are never modified or deleted
- **No network access** required for this data source
- **Data stays local** — never transmitted anywhere

### 2. Anthropic OAuth Usage API (online)

To show real-time quota percentages (5-hour and 7-day utilization), this tool calls Anthropic's own usage endpoint:

```
GET https://api.anthropic.com/api/oauth/usage
Authorization: Bearer <your-claude-code-oauth-token>
```

#### Token handling

| Question | Answer |
|----------|--------|
| Where does the token come from? | `~/.claude/.credentials.json` — Claude Code's own credential store |
| Where is it sent? | **Only** to `https://api.anthropic.com` (the token's issuer) |
| Is it cached to disk? | **No.** Only the API *response* (percentages, timestamps) is cached |
| Is it logged? | **No.** Debug logs never include the token value |
| What scopes does it use? | The tool only calls the `/api/oauth/usage` read-only endpoint |
| How long does it live? | ~12 hours. Claude Code auto-rotates it |
| Can I opt out? | Yes — if the credentials file is missing, the tool skips API calls and shows local data only |

#### What the API returns

The response contains **only** utilization metrics:

```json
{
  "five_hour": {"utilization": 76.0, "resets_at": "2026-04-02T20:00:00Z"},
  "seven_day": {"utilization": 13.0, "resets_at": "2026-04-09T11:00:00Z"}
}
```

No conversation content, no prompts, no personal information.

### 3. Cache file

API responses are cached to avoid excessive requests:

- **Location**: System temp directory (`claude-monitor-usage.json`)
- **Contents**: Utilization percentages and reset timestamps only
- **TTL**: 5 minutes, then automatically refreshed
- **Permissions**: Owner-only (`0600`) on Unix systems
- **No secrets**: The OAuth token is never written to this file

## What This Tool Does NOT Do

- Does **not** send data to any server other than `api.anthropic.com`
- Does **not** collect analytics, telemetry, or crash reports
- Does **not** modify any Claude Code configuration files
- Does **not** store, log, or transmit your OAuth token
- Does **not** read your conversations, prompts, or responses
- Does **not** require or accept an Anthropic API key
- Does **not** make inference calls or consume your quota

## File System Access

| Path | Access | Purpose |
|------|--------|---------|
| `~/.claude/projects/**/*.jsonl` | Read | Token usage history |
| `~/.claude/.credentials.json` | Read | OAuth token for usage API |
| `$TMPDIR/claude-monitor-usage.json` | Read/Write | Cached API response |
| `$TMPDIR/claude-monitor-usage.lock` | Read/Write | Prevents concurrent API calls |

No other files or directories are accessed.

## Reporting a Vulnerability

If you discover a security issue, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer directly with details
3. Allow reasonable time for a fix before disclosure

## Verification

This tool is open source. You can audit the complete token handling in:
- `src/claude_monitor_tool/data/api_client.py` — OAuth token read + API call
- `src/claude_monitor_tool/data/reader.py` — JSONL file reading (no network)
