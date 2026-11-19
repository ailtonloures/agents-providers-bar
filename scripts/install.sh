#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_UUID="agents-providers-bar@ailton.local"
EXT_SRC="$REPO_DIR/extension/$EXT_UUID"
EXT_DEST="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
BIN_DIR="$HOME/.local/bin"
BIN_PATH="$BIN_DIR/agents-usage"

mkdir -p "$BIN_DIR"
cat > "$BIN_PATH" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$REPO_DIR/backend\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m agents_usage.cli "\$@"
EOF
chmod +x "$BIN_PATH"

mkdir -p "$(dirname "$EXT_DEST")"
ln -sfn "$EXT_SRC" "$EXT_DEST"

if command -v gnome-extensions >/dev/null 2>&1; then
  if gnome-extensions enable "$EXT_UUID" 2>/dev/null; then
    echo "Enabled GNOME extension: $EXT_UUID"
  else
    echo "Extension linked at $EXT_DEST."
    echo "Note: On Wayland, log out and log back in, then run:"
    echo "  gnome-extensions enable $EXT_UUID"
  fi
fi

echo "Installed CLI at: $BIN_PATH"
echo "Test CLI with: $BIN_PATH --no-cache"
