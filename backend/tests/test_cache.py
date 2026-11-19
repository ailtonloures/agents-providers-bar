"""Unit tests for local usage cache and CLI fallback."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from agents_usage.cache import UsageCache
from agents_usage.cli import collect_provider
from agents_usage.models import ProviderUsage, QuotaWindow, UsageReport


class TestUsageCache(unittest.TestCase):
    def test_set_and_get_fresh_and_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = UsageCache(path=Path(tmp) / "usage.json", ttl_seconds=60)
            sample = ProviderUsage(
                provider="claude",
                display_name="Claude Code",
                status="ok",
                plan_name="Pro",
                windows=[QuotaWindow.from_used("5h Session", 20.0)],
            )
            cache.set(sample)
            loaded = cache.get("claude")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.from_cache)
            self.assertEqual(loaded.windows[0].used_percent, 20.0)

            expired_cache = UsageCache(path=Path(tmp) / "usage.json", ttl_seconds=-1)
            self.assertIsNone(expired_cache.get("claude", allow_stale=False))
            self.assertIsNotNone(expired_cache.get("claude", allow_stale=True))

    def test_collect_provider_falls_back_to_stale_on_rate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = UsageCache(path=Path(tmp) / "usage.json", ttl_seconds=-1)
            cache.set(
                ProviderUsage(
                    provider="claude",
                    display_name="Claude Code",
                    status="ok",
                    windows=[QuotaWindow.from_used("Weekly (7d)", 53.0)],
                )
            )

            def rate_limited_fetcher() -> ProviderUsage:
                return ProviderUsage(
                    provider="claude",
                    display_name="Claude Code",
                    status="rate_limited",
                    error_message="429",
                )

            result = collect_provider("claude", rate_limited_fetcher, cache, use_cache=False)
            self.assertEqual(result.status, "rate_limited")
            self.assertEqual(len(result.windows), 1)
            self.assertEqual(result.windows[0].used_percent, 53.0)

    def test_collect_provider_falls_back_to_stale_on_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = UsageCache(path=Path(tmp) / "usage.json", ttl_seconds=-1)
            future_reset = (datetime.now(timezone.utc) + timedelta(hours=2, minutes=15)).isoformat()
            cached_win = QuotaWindow.from_used(
                "Gemini 4 (Neon / Hydrogen)",
                35.0,
                resets_at=future_reset,
            )
            cached_win.reset_in_human = "stale-value"
            cache.set(
                ProviderUsage(
                    provider="antigravity",
                    display_name="Antigravity (Google AI)",
                    status="ok",
                    plan_name="Pro",
                    windows=[cached_win],
                )
            )

            def unavailable_fetcher() -> ProviderUsage:
                return ProviderUsage(
                    provider="antigravity",
                    display_name="Antigravity (Google AI)",
                    status="unavailable",
                    error_message="Antigravity daemon not running (start 'agy' or Antigravity IDE).",
                )

            result = collect_provider("antigravity", unavailable_fetcher, cache, use_cache=False)
            self.assertEqual(result.status, "unavailable")
            self.assertTrue(result.from_cache)
            self.assertEqual(result.plan_name, "Pro")
            self.assertEqual(len(result.windows), 1)
            self.assertEqual(result.windows[0].used_percent, 35.0)
            self.assertNotEqual(result.windows[0].reset_in_human, "stale-value")
            self.assertIsNotNone(result.windows[0].reset_in_human)

            report = UsageReport(providers=[result])
            self.assertEqual(report.overall_max_used_percent, 35.0)


if __name__ == "__main__":
    unittest.main()
