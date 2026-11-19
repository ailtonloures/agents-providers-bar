"""Local JSON file cache for provider usage responses."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .models import ProviderUsage

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "agents-providers-bar" / "usage.json"
DEFAULT_TTL_SECONDS = 300


class UsageCache:
    """Reads and writes cached provider usage snapshots."""

    def __init__(
        self,
        path: Path = DEFAULT_CACHE_PATH,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, provider: str, allow_stale: bool = False) -> ProviderUsage | None:
        """Return cached ProviderUsage if present and fresh (or stale if allowed)."""
        raw = self._load_raw()
        entry = raw.get(provider)
        if not isinstance(entry, dict):
            return None

        cached_at = entry.get("cached_at", 0)
        age = time.time() - float(cached_at)
        if not allow_stale and age > self.ttl_seconds:
            return None

        payload = entry.get("data")
        if not isinstance(payload, dict):
            return None

        usage = ProviderUsage.from_dict(payload)
        usage.from_cache = True
        return usage

    def set(self, usage: ProviderUsage) -> None:
        """Persist a ProviderUsage entry atomically."""
        raw = self._load_raw()
        raw[usage.provider] = {
            "cached_at": time.time(),
            "data": usage.to_dict(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        os.replace(tmp_path, self.path)
