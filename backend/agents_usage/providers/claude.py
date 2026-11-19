"""Claude Code subscription usage fetcher via local OAuth credentials."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from ..models import ProviderUsage, QuotaWindow

DEFAULT_CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

WINDOW_LABELS: tuple[tuple[str, str], ...] = (
    ("five_hour", "5h Session"),
    ("seven_day", "Weekly (7d)"),
    ("seven_day_sonnet", "Weekly Sonnet"),
    ("seven_day_opus", "Weekly Opus"),
)


def _read_oauth_info(credentials_path: Path) -> tuple[str | None, str | None]:
    if not credentials_path.exists():
        return None, None
    data = json.loads(credentials_path.read_text(encoding="utf-8"))
    oauth = data.get("claudeAiOauth") if isinstance(data.get("claudeAiOauth"), dict) else data
    token = oauth.get("accessToken")
    sub_type = oauth.get("subscriptionType")
    plan_name = str(sub_type).capitalize() if sub_type else None
    return token, plan_name


def _default_http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return resp.status, body


def parse_claude_usage(payload: dict[str, Any], plan_name: str | None = None) -> ProviderUsage:
    """Convert raw /api/oauth/usage JSON into ProviderUsage."""
    windows: list[QuotaWindow] = []
    for key, label in WINDOW_LABELS:
        bucket = payload.get(key)
        if not isinstance(bucket, dict):
            continue
        utilization = bucket.get("utilization")
        if utilization is None:
            continue
        windows.append(
            QuotaWindow.from_used(
                label=label,
                used_percent=float(utilization),
                resets_at=bucket.get("resets_at"),
            )
        )

    return ProviderUsage(
        provider="claude",
        display_name="Claude Code",
        status="ok",
        plan_name=plan_name,
        windows=windows,
    )


def fetch_claude_usage(
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
    http_get: Callable[[str, dict[str, str], float], tuple[int, dict[str, Any]]] = _default_http_get,
    timeout: float = 8.0,
) -> ProviderUsage:
    """Fetch Claude Code subscription usage from Anthropic OAuth usage endpoint."""
    try:
        token, plan_name = _read_oauth_info(credentials_path)
    except (OSError, json.JSONDecodeError) as exc:
        return ProviderUsage(
            provider="claude",
            display_name="Claude Code",
            status="error",
            error_message=f"Failed to read credentials: {exc}",
        )

    if not token:
        return ProviderUsage(
            provider="claude",
            display_name="Claude Code",
            status="unauthenticated",
            error_message="Run 'claude' to sign in (~/.claude/.credentials.json missing)",
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
        "User-Agent": "claude-cli/2.1.0",
    }

    try:
        _, payload = http_get(CLAUDE_USAGE_URL, headers, timeout)
        return parse_claude_usage(payload, plan_name=plan_name)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return ProviderUsage(
                provider="claude",
                display_name="Claude Code",
                status="unauthenticated",
                plan_name=plan_name,
                error_message="OAuth token expired. Run 'claude' to refresh.",
            )
        if exc.code == 429:
            return ProviderUsage(
                provider="claude",
                display_name="Claude Code",
                status="rate_limited",
                plan_name=plan_name,
                error_message="Rate limited by Anthropic usage API (429).",
            )
        return ProviderUsage(
            provider="claude",
            display_name="Claude Code",
            status="error",
            plan_name=plan_name,
            error_message=f"HTTP {exc.code} from Anthropic usage API.",
        )
    except Exception as exc:  # noqa: BLE001 - surface clean status to UI
        return ProviderUsage(
            provider="claude",
            display_name="Claude Code",
            status="error",
            plan_name=plan_name,
            error_message=f"Network error: {exc}",
        )
