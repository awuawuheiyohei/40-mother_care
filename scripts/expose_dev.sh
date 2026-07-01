#!/usr/bin/env bash
# Expose local FastAPI service to public HTTPS via cloudflared or ngrok.
# Usage:
#   bash scripts/expose_dev.sh           # auto-detect cloudflared > ngrok
#   bash scripts/expose_dev.sh cloudflared
#   bash scripts/expose_dev.sh ngrok
#
# Output: prints the public HTTPS URL once it's established.
# Note: the URL is ephemeral — restart the script to get a new one.

set -euo pipefail

cd "$(dirname "$0")/.."

TOOL="${1:-auto}"

detect_tool() {
  if command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared"
  elif command -v ngrok >/dev/null 2>&1; then
    echo "ngrok"
  else
    echo ""
  fi
}

if [ "$TOOL" = "auto" ]; then
  TOOL="$(detect_tool)"
fi

if [ -z "$TOOL" ]; then
  echo "Neither cloudflared nor ngrok is installed."
  echo ""
  echo "Install one of:"
  echo "  brew install cloudflared        # recommended — no signup, free"
  echo "  brew install ngrok              # requires free signup at dashboard.ngrok.com"
  exit 1
fi

PORT="${APP_PORT:-8000}"

case "$TOOL" in
  cloudflared)
    echo "==> Starting cloudflared tunnel to http://localhost:$PORT"
    echo "    The public HTTPS URL will be printed below (line starting with https://)"
    echo "    Press Ctrl+C to stop."
    echo ""
    exec cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT"
    ;;
  ngrok)
    echo "==> Starting ngrok tunnel to http://localhost:$PORT"
    echo "    The public HTTPS URL will be at https://<random>.ngrok-free.app"
    echo "    Press Ctrl+C to stop."
    echo ""
    exec ngrok http "$PORT" --domain "${NGROK_DOMAIN:-}" 2>/dev/null \
      || ngrok http "$PORT"
    ;;
  *)
    echo "Unknown tool: $TOOL"
    exit 1
    ;;
esac