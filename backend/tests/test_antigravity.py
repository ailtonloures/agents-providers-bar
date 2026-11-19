"""Unit tests for Antigravity usage fetcher."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agents_usage.providers.antigravity import fetch_antigravity_usage, parse_antigravity_usage


class TestAntigravityProvider(unittest.TestCase):
    def test_parse_groups_models_by_bucket(self) -> None:
        payload = {
            "userStatus": {
                "planStatus": {"planInfo": {"planName": "Pro"}},
                "cascadeModelConfigData": {
                    "clientModelConfigs": [
                        {
                            "label": "Gemini 4 Neon (High)",
                            "quotaInfo": {"remainingFraction": 0.85, "resetTime": "2099-01-01T10:00:00Z"},
                        },
                        {
                            "label": "Gemini 4 Hydrogen (Medium)",
                            "quotaInfo": {"remainingFraction": 0.90, "resetTime": "2099-01-01T10:00:00Z"},
                        },
                        {
                            "label": "Gemini 4 Argon (High)",
                            "quotaInfo": {"remainingFraction": 1.0, "resetTime": "2099-01-07T10:00:00Z"},
                        },
                    ]
                },
            }
        }
        usage = parse_antigravity_usage(payload)
        self.assertEqual(usage.status, "ok")
        self.assertEqual(usage.plan_name, "Pro")
        self.assertEqual(len(usage.windows), 2)
        neon_bucket = next(w for w in usage.windows if "Neon" in w.label)
        self.assertEqual(neon_bucket.used_percent, 15.0)
        argon_bucket = next(w for w in usage.windows if "Argon" in w.label)
        self.assertEqual(argon_bucket.used_percent, 0.0)

    def test_missing_daemon_returns_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usage = fetch_antigravity_usage(daemon_dir=Path(tmp))
        self.assertEqual(usage.status, "unavailable")

    def test_hub_discovery_and_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            daemon_dir = Path(tmp)
            hub_file = daemon_dir / "hub_12345.json"
            hub_file.write_text(
                json.dumps({"pid": os.getpid(), "httpPort": 12345, "csrfToken": "csrf-xyz"}),
                encoding="utf-8",
            )

            def fake_post(url: str, headers: dict[str, str], _timeout: float):
                self.assertIn("12345", url)
                self.assertEqual(headers["X-Codeium-Csrf-Token"], "csrf-xyz")
                return {
                    "userStatus": {
                        "planStatus": {"planInfo": {"planName": "Pro"}},
                        "cascadeModelConfigData": {"clientModelConfigs": []},
                    }
                }

            usage = fetch_antigravity_usage(daemon_dir=daemon_dir, http_post=fake_post)
        self.assertEqual(usage.status, "ok")
        self.assertEqual(usage.plan_name, "Pro")


if __name__ == "__main__":
    unittest.main()
