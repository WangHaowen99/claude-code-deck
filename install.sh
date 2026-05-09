#!/usr/bin/env bash
set -euo pipefail

REPO_RAW_URL="${CCD_RAW_URL:-https://raw.githubusercontent.com/WangHaowen99/claude-code-deck/develop/ccd}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$INSTALL_DIR/ccd"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing dependency: $1" >&2
    exit 1
  fi
}

need python3
need tmux
need claude

mkdir -p "$INSTALL_DIR"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$REPO_RAW_URL" -o "$TARGET"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$TARGET" "$REPO_RAW_URL"
else
  echo "Missing dependency: curl or wget" >&2
  exit 1
fi

chmod +x "$TARGET"

echo "Installed ccd to $TARGET"
case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *)
    echo "Note: $INSTALL_DIR is not in PATH."
    echo "Add this to your shell profile:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
    ;;
esac

if [ "${CCD_SKIP_INIT:-0}" != "1" ]; then
  "$TARGET" init
else
  echo "Skipped init because CCD_SKIP_INIT=1."
fi

