"""CLI entrypoint for agents-usage."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .cache import DEFAULT_TTL_SECONDS, UsageCache
from .models import ProviderUsage, UsageReport, format_reset_in
from .providers import fetch_antigravity_usage, fetch_claude_usage

PROVIDERS: dict[str, Callable[[], ProviderUsage]] = {
    "claude": fetch_claude_usage,
    "antigravity": fetch_antigravity_usage,
}


def collect_provider(
    name: str,
    fetcher: Callable[[], ProviderUsage],
    cache: UsageCache,
    use_cache: bool,
) -> ProviderUsage:
    """Collect usage for a single provider with cache + stale fallback on rate limit."""
    if use_cache:
        cached = cache.get(name, allow_stale=False)
        if cached is not None:
            return cached

    fresh = fetcher()
    if fresh.status == "ok":
        cache.set(fresh)
        return fresh

    if fresh.status in ("rate_limited", "error", "unavailable"):
        stale = cache.get(name, allow_stale=True)
        if stale is not None and stale.windows:
            stale.status = fresh.status
            stale.error_message = fresh.error_message
            for win in stale.windows:
                if win.resets_at:
                    win.reset_in_human = format_reset_in(win.resets_at)
            return stale

    return fresh


def build_report(
    provider_names: list[str] | None = None,
    use_cache: bool = True,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> UsageReport:
    """Fetch all requested providers in parallel and return a UsageReport."""
    selected = provider_names or list(PROVIDERS.keys())
    cache = UsageCache(ttl_seconds=ttl_seconds)

    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futures = {
            name: pool.submit(collect_provider, name, PROVIDERS[name], cache, use_cache)
            for name in selected
        }
        results = [futures[name].result() for name in selected]

    return UsageReport(providers=results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Claude Code and Antigravity usage quotas.")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--no-cache", action="store_true", help="Bypass local cache")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS, help="Cache TTL in seconds")
    parser.add_argument(
        "--provider",
        choices=list(PROVIDERS.keys()),
        action="append",
        help="Filter to specific provider(s)",
    )
    args = parser.parse_args(argv)

    report = build_report(
        provider_names=args.provider,
        use_cache=not args.no_cache,
        ttl_seconds=args.ttl,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for prov in report.providers:
            plan = f" ({prov.plan_name})" if prov.plan_name else ""
            print(f"=== {prov.display_name}{plan} [{prov.status}] ===")
            if prov.error_message:
                print(f"  ! {prov.error_message}")
            for win in prov.windows:
                reset_str = f" | resets in {win.reset_in_human}" if win.reset_in_human else ""
                print(f"  - {win.label}: {win.used_percent:.0f}% used{reset_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
