#!/usr/bin/env bash
set -euo pipefail

EXT_UUID="agents-providers-bar@ailton.local"
EXT_DEST="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
BIN_PATH="$HOME/.local/bin/agents-usage"

if command -v gnome-extensions >/dev/null 2>&1; then
  gnome-extensions disable "$EXT_UUID" 2>/dev/null || true
fi

rm -f "$EXT_DEST" "$BIN_PATH"
echo "Uninstalled $EXT_UUID and $BIN_PATH"
