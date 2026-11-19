# GEMINI.md

Context instructions and project standards for **Agents Providers Usage Bar** for the Antigravity agent.

## Project Overview

Subscription quota monitor for **Claude Code** and **Antigravity (Google AI)** composed of:
- **Python Backend (`backend/agents_usage/`)**: `agents-usage` CLI that queries providers in parallel, applies local caching at `~/.cache/agents-providers-bar/usage.json`, and returns normalized data in text or JSON.
- **GNOME Shell 46 Extension (`extension/agents-providers-bar@ailton.local/`)**: top-bar indicator written in GJS (ESM) that invokes `agents-usage --json` via `Gio.Subprocess` and renders usage cards in a popup.

## Architecture and Key Files

- `pyproject.toml`: packaging for the `agents_usage` package (from `backend/`), script `agents-usage = "agents_usage.cli:main"`, Python `>= 3.10`, **no external dependencies**.
- `backend/agents_usage/models.py`: `QuotaWindow`, `ProviderUsage`, `UsageReport`, and `format_reset_in`.
- `backend/agents_usage/cache.py`: `UsageCache` (default TTL `300s`, atomic write via `.tmp` + `os.replace`).
- `backend/agents_usage/cli.py`: `collect_provider`, `build_report`, `main`. On `rate_limited` or `error`, falls back to *stale* cache if saved windows exist.
- `backend/agents_usage/providers/claude.py`: reads `~/.claude/.credentials.json` and queries `https://api.anthropic.com/api/oauth/usage`.
- `backend/agents_usage/providers/antigravity.py`: discovers hubs in `~/.gemini/antigravity/daemon/hub_*.json` (prioritizing live PIDs) and queries `GetUserStatus` via local HTTP.
- `extension/agents-providers-bar@ailton.local/extension.js`: GJS UI (`AgentsUsageIndicator`), 300s timer, and card rendering.
- `scripts/install.sh` and `scripts/uninstall.sh`: installation/removal of the `~/.local/bin/agents-usage` wrapper and the GNOME extension symlink.

## Main Commands

- **Validate everything (lint + tests)**: `make check`
- **Unit tests**: `make test` (or `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v`)
- **Extension lint**: `make lint` (`node --check` on `extension.js` + `json.tool` on `metadata.json`)
- **Run CLI**: `make run` or `make json`
- **Install / Uninstall**: `make install` / `make uninstall`

## Development Conventions and Rules

1. **Zero external dependencies in the backend**: keep `dependencies = []` in `pyproject.toml`. Use only the Python standard library.
2. **Error handling in providers**: `fetch_*_usage` functions must not propagate unhandled exceptions to the CLI/UI; return a `ProviderUsage` with the appropriate `status` (`"ok"`, `"rate_limited"`, `"unauthenticated"`, `"unavailable"`, or `"error"`) and a descriptive `error_message`.
3. **Testability**: keep simple dependency injection in collectors (`credentials_path`/`daemon_dir`, `http_get`/`http_post`) so `backend/tests/` continues running isolated without network or a real daemon.
4. **GNOME Shell 46 compatibility**: `extension.js` must use ESM imports (`import ... from 'gi://...'` and `resource:///org/gnome/shell/...`) and remain compatible with `node --check`.
5. **Mandatory verification**: after any change to Python code or the extension, run `make check` before finishing.
