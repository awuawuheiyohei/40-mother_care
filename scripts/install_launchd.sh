#!/usr/bin/env bash
# Install mother_care services as macOS launchd daemons.
# After install, services will auto-restart on crash and survive reboot/login.
#
# Usage: bash scripts/install_launchd.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$PROJECT_DIR/data"

UVICORN_PLIST="$LAUNCH_AGENTS_DIR/com.mothercare.uvicorn.plist"
NGROK_PLIST="$LAUNCH_AGENTS_DIR/com.mothercare.ngrok.plist"
CF_PLIST_LEGACY="$LAUNCH_AGENTS_DIR/com.mothercare.cloudflared.plist"

# 1. Stop any running instances via launchctl
echo "==> Stopping existing instances..."
launchctl unload "$UVICORN_PLIST" 2>/dev/null || true
launchctl unload "$NGROK_PLIST" 2>/dev/null || true
launchctl unload "$CF_PLIST_LEGACY" 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
pkill -f "ngrok http" 2>/dev/null || true
sleep 2

# 2. Remove legacy cloudflared plist if present
if [ -f "$CF_PLIST_LEGACY" ]; then
    echo "==> Removing legacy cloudflared plist..."
    rm -f "$CF_PLIST_LEGACY"
fi

# 3. Copy fresh plists
echo "==> Installing launchd plists..."
cp "$PROJECT_DIR/deploy/com.mothercare.uvicorn.plist" "$UVICORN_PLIST"
cp "$PROJECT_DIR/deploy/com.mothercare.ngrok.plist" "$NGROK_PLIST"
chmod 644 "$UVICORN_PLIST" "$NGROK_PLIST"

# 4. Load plists
echo "==> Loading services..."
launchctl load -w "$UVICORN_PLIST"
launchctl load -w "$NGROK_PLIST"

echo ""
echo "==> Done. Services should be running."
echo "    Check status:  bash scripts/status_services.sh"
echo "    View logs:"
echo "      tail -f $PROJECT_DIR/data/uvicorn.log"
echo "      tail -f $PROJECT_DIR/data/ngrok.log"