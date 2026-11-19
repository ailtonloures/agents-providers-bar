# Agents Providers Usage Bar

A **GNOME Shell 46** (Ubuntu) top-bar extension paired with a **Python CLI** (`agents-usage`) for real-time monitoring of **Claude Code** and **Antigravity (Google AI)** subscription usage quotas.

<p align="center">
  <img src="assets/image.png" alt="Agents Providers Usage Bar extension showing the Claude Code and Antigravity quota popup in GNOME Shell" />
</p>

## Overview

This project solves the problem of tracking AI assistant usage limits and reset windows directly from the Linux desktop without opening terminals or web dashboards. It consists of two decoupled layers:

1. **Backend / CLI (`agents-usage`)**: queries providers in parallel, normalizes the data into a unified format, applies local caching, and outputs the result as plain text or JSON.
2. **GNOME Shell Extension (`agents-providers-bar@ailton.local`)**: asynchronously consumes the CLI JSON output, displays a discreet top-bar icon with color-coded severity, and renders a popup menu with detailed per-provider cards.

## Features

- **Top-bar status indicator**: symbolic icon that changes color based on the highest usage percentage among active providers:
  - **Green**: `< 60%`
  - **Amber**: `60% – 84.9%`
  - **Red**: `>= 85%`
  - **Gray (muted)**: no data available or error
- **Detailed popup menu**:
  - Individual provider cards with name, plan (`plan_name`), and status.
  - Progress bars per quota window (e.g., `5h Session`, `Weekly (7d)`, Antigravity model buckets).
  - Formatted countdown to the next reset (e.g., `2h 15m`, `3d 4h`).
- **Automatic and manual refresh**:
  - Automatically refreshes every **5 minutes** (`300s`).
  - **Refresh** button in the popup header to force a fresh query bypassing the cache (`--no-cache`).
- **Local cache and fault tolerance**:
  - Cache stored at `~/.cache/agents-providers-bar/usage.json` (default TTL of `300s`), written atomically.
  - On *rate limit* (`429`) or transient errors, falls back to the last cached snapshot (*stale*) while preserving previous window data.

## Architecture

### Python Backend (`backend/agents_usage/`)

- **Zero external dependencies**: uses only the Python standard library (`>= 3.10`), including `urllib.request`, `json`, `argparse`, `dataclasses`, `concurrent.futures`, and `pathlib`. Packaged with `pyproject.toml` and managed via `uv`.
- **`cli.py`**: `agents-usage` entrypoint. Runs provider collection in parallel using `ThreadPoolExecutor`, coordinates cache reads/writes, and prints formatted or JSON (`--json`) output.
- **`models.py`**: defines `QuotaWindow`, `ProviderUsage`, and `UsageReport`, as well as remaining reset time formatting (`format_reset_in`).
- **`cache.py`**: implements `UsageCache` with atomic writes via a `.tmp` file + `os.replace`.
- **`providers/claude.py`**:
  - Reads the OAuth token and subscription type from `~/.claude/.credentials.json`.
  - Queries `https://api.anthropic.com/api/oauth/usage` and converts buckets (`five_hour`, `seven_day`, `seven_day_sonnet`, `seven_day_opus`) into `QuotaWindow` entries.
- **`providers/antigravity.py`**:
  - Discovers local Antigravity daemon instances in `~/.gemini/antigravity/daemon/hub_*.json`, prioritizing processes with an active `pid`.
  - Makes a local RPC call (`POST http://127.0.0.1:<httpPort>/exa.language_server_pb.LanguageServerService/GetUserStatus`) using the `X-Codeium-Csrf-Token` header.
  - Groups returned models into buckets (such as `Gemini 4 (Neon / Hydrogen)`, `Gemini 4 Argon`, `Gemini Flash`, `Claude (Antigravity)`, `GPT-OSS`) using the highest usage per bucket.

### GNOME Shell Extension (`extension/agents-providers-bar@ailton.local/`)

- Written in **GJS (ESM)** for GNOME Shell 46 (`metadata.json` with `"shell-version": ["46"]`).
- **`extension.js`**: registers `AgentsUsageIndicator` (`PanelMenu.Button`), runs `~/.local/bin/agents-usage --json` (falling back to `agents-usage` on `PATH`) via asynchronous `Gio.Subprocess`, and dynamically builds cards with `St` widgets.
- **`stylesheet.css`** and **`icons/provider-bar-symbolic.svg`**: styling for the popup, progress bars, and top-bar symbolic icon.

## Repository Structure

```text
.
├── Makefile
├── pyproject.toml
├── uv.lock
├── assets/
│   └── image.png               # Screenshot of the running extension
├── backend/
│   ├── agents_usage/
│   │   ├── cli.py              # CLI entrypoint and parallel orchestration
│   │   ├── cache.py            # Local JSON cache with atomic writes
│   │   ├── models.py           # QuotaWindow, ProviderUsage, UsageReport models
│   │   └── providers/
│   │       ├── claude.py       # Claude Code OAuth collector
│   │       └── antigravity.py  # Antigravity local RPC collector
│   └── tests/
│       ├── test_antigravity.py
│       ├── test_cache.py
│       └── test_claude.py
├── extension/
│   └── agents-providers-bar@ailton.local/
│       ├── extension.js        # GNOME Shell 46 indicator and popup
│       ├── metadata.json       # Extension metadata
│       ├── stylesheet.css      # Popup and icon styles
│       └── icons/
│           └── provider-bar-symbolic.svg
└── scripts/
    ├── install.sh              # Installs CLI + extension symlink
    └── uninstall.sh            # Removes CLI and disables/removes extension
```

## Prerequisites

- Ubuntu with **GNOME Shell 46**
- **Python >= 3.10**
- **`uv`** (recommended for running tests and commands via `Makefile`)
- **Node.js** (used only in `make lint` for syntax validation of `extension.js`)
- For live provider data:
  - **Claude Code**: locally authenticated (`~/.claude/.credentials.json` generated by the `claude` command).
  - **Antigravity**: local daemon running (started by `agy` or the Antigravity IDE).

## Installation

Run the installation script (or via `Makefile`):

```bash
./scripts/install.sh
# or
make install
```

The script performs the following actions:
1. Creates the wrapper executable at `~/.local/bin/agents-usage` pointing to `backend/` with `PYTHONPATH`.
2. Creates a symlink for the extension at `~/.local/share/gnome-shell/extensions/agents-providers-bar@ailton.local`.
3. Attempts to enable the extension via `gnome-extensions enable agents-providers-bar@ailton.local`.

> **Note on Wayland:** if GNOME Shell does not recognize the extension immediately after installation, log out and log back in, then run:
> ```bash
> gnome-extensions enable agents-providers-bar@ailton.local
> ```

### Uninstallation

```bash
./scripts/uninstall.sh
# or
make uninstall
```

## Commands

### CLI (`agents-usage`)

```bash
# Terminal-formatted output (uses 300s cache by default)
agents-usage

# JSON output bypassing the cache
agents-usage --json --no-cache

# Filter by a specific provider
agents-usage --provider claude
agents-usage --provider antigravity

# Set a custom cache TTL (in seconds)
agents-usage --ttl 60
```

### `Makefile` Shortcuts

| Command | Description |
| :--- | :--- |
| `make run` | Runs `uv run agents-usage --no-cache` |
| `make json` | Runs `uv run agents-usage --json --no-cache` |
| `make test` | Runs the unit test suite with `uv` |
| `make lint` | Validates JS syntax (`node --check`) and JSON (`metadata.json`) |
| `make check` | Runs `lint` and `test` |
| `make install` | Runs `./scripts/install.sh` |
| `make uninstall` | Runs `./scripts/uninstall.sh` |

## Testing

### 1. Full Check (Lint + Unit Tests)

```bash
make check
```

Or run them individually:

```bash
# Unit tests only (via uv)
make test

# Unit tests only (without uv, using system python3)
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v

# Extension lint only (JS + metadata.json)
make lint
```

### 2. Test the Backend Locally

```bash
make json
```

Verify that the returned JSON contains `overall_max_used_percent` and the `providers` list with the expected statuses (`ok`, `unauthenticated`, `unavailable`, etc.).

### 3. Debug the GNOME Shell Extension

To follow extension logs or errors in real time on Ubuntu:

```bash
journalctl -f /usr/bin/gnome-shell
```
