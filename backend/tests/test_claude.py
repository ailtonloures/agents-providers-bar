"""Unit tests for Claude Code usage fetcher."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from agents_usage.providers.claude import fetch_claude_usage, parse_claude_usage


class TestClaudeProvider(unittest.TestCase):
    def test_parse_claude_usage(self) -> None:
        payload = {
            "five_hour": {"utilization": 24.5, "resets_at": "2099-01-01T05:00:00+00:00"},
            "seven_day": {"utilization": 53.0, "resets_at": "2099-01-04T11:00:00+00:00"},
            "seven_day_sonnet": None,
        }
        usage = parse_claude_usage(payload, plan_name="Pro")
        self.assertEqual(usage.status, "ok")
        self.assertEqual(usage.plan_name, "Pro")
        self.assertEqual(len(usage.windows), 2)
        self.assertEqual(usage.windows[0].label, "5h Session")
        self.assertEqual(usage.windows[0].used_percent, 24.5)
        self.assertEqual(usage.windows[1].label, "Weekly (7d)")
        self.assertEqual(usage.windows[1].used_percent, 53.0)

    def test_missing_credentials_returns_unauthenticated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usage = fetch_claude_usage(credentials_path=Path(tmp) / "missing.json")
        self.assertEqual(usage.status, "unauthenticated")
        self.assertEqual(usage.windows, [])

    def test_rate_limit_429(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            creds_path = Path(tmp) / ".credentials.json"
            creds_path.write_text(
                json.dumps({"claudeAiOauth": {"accessToken": "tok", "subscriptionType": "pro"}}),
                encoding="utf-8",
            )

            def fake_get(_url: str, _headers: dict[str, str], _timeout: float):
                raise urllib.error.HTTPError(_url, 429, "Too Many Requests", {}, None)

            usage = fetch_claude_usage(credentials_path=creds_path, http_get=fake_get)
        self.assertEqual(usage.status, "rate_limited")
        self.assertEqual(usage.plan_name, "Pro")


if __name__ == "__main__":
    unittest.main()
