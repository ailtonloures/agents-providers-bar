"""Normalized data models for provider usage and quota windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def format_reset_in(resets_at: str | None, now: datetime | None = None) -> str | None:
    """Format an ISO-8601 reset timestamp into a compact human countdown."""
    if not resets_at:
        return None
    try:
        target = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)

    ref = now or datetime.now(timezone.utc)
    delta_seconds = int((target - ref).total_seconds())
    if delta_seconds <= 0:
        return "now"

    days, rem = divmod(delta_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{max(1, minutes)}m"


@dataclass
class QuotaWindow:
    """Single quota window (e.g., 5h session, weekly, or model bucket)."""

    label: str
    used_percent: float
    remaining_percent: float
    resets_at: str | None = None
    reset_in_human: str | None = None

    @classmethod
    def from_used(
        cls,
        label: str,
        used_percent: float,
        resets_at: str | None = None,
        now: datetime | None = None,
    ) -> "QuotaWindow":
        clamped_used = round(max(0.0, min(100.0, float(used_percent))), 1)
        remaining = round(max(0.0, 100.0 - clamped_used), 1)
        return cls(
            label=label,
            used_percent=clamped_used,
            remaining_percent=remaining,
            resets_at=resets_at,
            reset_in_human=format_reset_in(resets_at, now=now),
        )


@dataclass
class ProviderUsage:
    """Usage summary for a single AI subscription provider."""

    provider: str
    display_name: str
    status: str  # "ok" | "rate_limited" | "unauthenticated" | "unavailable" | "error"
    plan_name: str | None = None
    windows: list[QuotaWindow] = field(default_factory=list)
    error_message: str | None = None
    fetched_at: str = field(default_factory=utc_now_iso)
    from_cache: bool = False

    @property
    def max_used_percent(self) -> float:
        """Return the highest utilization percentage across all windows."""
        if not self.windows:
            return 0.0
        return max(w.used_percent for w in self.windows)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["max_used_percent"] = self.max_used_percent
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderUsage":
        windows = [QuotaWindow(**w) for w in data.get("windows", [])]
        return cls(
            provider=data["provider"],
            display_name=data["display_name"],
            status=data["status"],
            plan_name=data.get("plan_name"),
            windows=windows,
            error_message=data.get("error_message"),
            fetched_at=data.get("fetched_at", utc_now_iso()),
            from_cache=bool(data.get("from_cache", False)),
        )


@dataclass
class UsageReport:
    """Top-level report returned to the GNOME extension and CLI."""

    providers: list[ProviderUsage]
    generated_at: str = field(default_factory=utc_now_iso)

    @property
    def overall_max_used_percent(self) -> float:
        ok_values = [
            p.max_used_percent
            for p in self.providers
            if p.windows and p.status in ("ok", "rate_limited", "unavailable")
        ]
        return max(ok_values) if ok_values else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall_max_used_percent": self.overall_max_used_percent,
            "providers": [p.to_dict() for p in self.providers],
        }
