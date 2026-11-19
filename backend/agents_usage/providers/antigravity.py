"""Antigravity (Google AI) usage fetcher via local Antigravity hub RPC."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from ..models import ProviderUsage, QuotaWindow

DEFAULT_DAEMON_DIR = Path.home() / ".gemini" / "antigravity" / "daemon"
GET_USER_STATUS_PATH = "/exa.language_server_pb.LanguageServerService/GetUserStatus"

BUCKET_RULES: tuple[tuple[str, str], ...] = (
    ("Neon", "Gemini 4 (Neon / Hydrogen)"),
    ("Hydrogen", "Gemini 4 (Neon / Hydrogen)"),
    ("Argon", "Gemini 4 Argon"),
    ("Flash", "Gemini Flash"),
    ("Claude", "Claude (Antigravity)"),
    ("GPT", "GPT-OSS"),
)


def _is_pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _discover_hubs(daemon_dir: Path) -> list[dict[str, Any]]:
    if not daemon_dir.exists():
        return []
    hubs: list[dict[str, Any]] = []
    for path in sorted(daemon_dir.glob("hub_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("httpPort") and data.get("csrfToken"):
            hubs.append(data)

    # Prefer hubs whose process is still alive
    alive = [h for h in hubs if _is_pid_alive(h.get("pid"))]
    return alive or hubs


def _default_http_post(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _bucket_name(label: str) -> str:
    for needle, bucket in BUCKET_RULES:
        if needle.lower() in label.lower():
            return bucket
    return re.sub(r"\s*\([^)]*\)\s*$", "", label).strip() or label


def parse_antigravity_usage(payload: dict[str, Any]) -> ProviderUsage:
    """Parse GetUserStatus JSON payload into normalized ProviderUsage."""
    user_status = payload.get("userStatus", {})
    plan_info = user_status.get("planStatus", {}).get("planInfo", {})
    plan_name = plan_info.get("planName")

    configs = user_status.get("cascadeModelConfigData", {}).get("clientModelConfigs", [])
    buckets: dict[str, tuple[float, str | None]] = {}

    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        label = cfg.get("label")
        quota = cfg.get("quotaInfo")
        if not label or not isinstance(quota, dict):
            continue
        remaining_fraction = quota.get("remainingFraction")
        if remaining_fraction is None:
            continue

        bucket = _bucket_name(str(label))
        used_percent = (1.0 - float(remaining_fraction)) * 100.0
        reset_time = quota.get("resetTime")

        existing = buckets.get(bucket)
        if existing is None or used_percent > existing[0]:
            buckets[bucket] = (used_percent, reset_time)

    windows = [
        QuotaWindow.from_used(label=bucket, used_percent=used, resets_at=reset_time)
        for bucket, (used, reset_time) in buckets.items()
    ]

    return ProviderUsage(
        provider="antigravity",
        display_name="Antigravity (Google AI)",
        status="ok",
        plan_name=plan_name,
        windows=windows,
    )


def fetch_antigravity_usage(
    daemon_dir: Path = DEFAULT_DAEMON_DIR,
    http_post: Callable[[str, dict[str, str], float], dict[str, Any]] = _default_http_post,
    timeout: float = 5.0,
) -> ProviderUsage:
    """Fetch Antigravity quota from the running local Antigravity hub."""
    hubs = _discover_hubs(daemon_dir)
    if not hubs:
        return ProviderUsage(
            provider="antigravity",
            display_name="Antigravity (Google AI)",
            status="unavailable",
            error_message="Antigravity daemon not running (start 'agy' or Antigravity IDE).",
        )

    last_error: str | None = None
    for hub in hubs:
        port = hub["httpPort"]
        url = f"http://127.0.0.1:{port}{GET_USER_STATUS_PATH}"
        headers = {
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
            "X-Codeium-Csrf-Token": str(hub["csrfToken"]),
        }
        try:
            payload = http_post(url, headers, timeout)
            return parse_antigravity_usage(payload)
        except Exception as exc:  # noqa: BLE001 - try next hub or report cleanly
            last_error = str(exc)

    return ProviderUsage(
        provider="antigravity",
        display_name="Antigravity (Google AI)",
        status="unavailable",
        error_message=f"Could not reach Antigravity hub: {last_error}",
    )
