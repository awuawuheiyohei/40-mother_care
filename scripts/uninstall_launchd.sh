#!/usr/bin/env bash
# Uninstall mother_care launchd services.

set -euo pipefail

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
UVICORN_PLIST="$LAUNCH_AGENTS_DIR/com.mothercare.uvicorn.plist"
CF_PLIST="$LAUNCH_AGENTS_DIR/com.mothercare.cloudflared.plist"

echo "==> Unloading services..."
launchctl unload "$UVICORN_PLIST" 2>/dev/null || true
launchctl unload "$CF_PLIST" 2>/dev/null || true

echo "==> Removing plist files..."
rm -f "$UVICORN_PLIST" "$CF_PLIST"

echo "==> Done. To reinstall: bash scripts/install_launchd.sh"