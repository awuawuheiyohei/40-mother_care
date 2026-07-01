#!/usr/bin/env bash
# Show mother_care service status + current public URL.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data"

# ngrok reserved domain — must match deploy/com.mothercare.ngrok.plist
NGROK_DOMAIN="${NGROK_DOMAIN:-matcher-cufflink-penpal.ngrok-free.dev}"

echo "=== launchd status ==="
if launchctl list | grep -q com.mothercare.uvicorn; then
    PID=$(launchctl list | grep com.mothercare.uvicorn | awk '{print $1}')
    echo "  uvicorn     : loaded (pid $PID)"
else
    echo "  uvicorn     : NOT LOADED"
fi

if launchctl list | grep -q com.mothercare.ngrok; then
    PID=$(launchctl list | grep com.mothercare.ngrok | awk '{print $1}')
    echo "  ngrok       : loaded (pid $PID)"
else
    echo "  ngrok       : NOT LOADED"
fi

if launchctl list | grep -q com.mothercare.cloudflared; then
    echo "  cloudflared : STILL LOADED (legacy — should be removed)"
fi

echo ""
echo "=== local service ==="
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "  port 8000   : listening"
else
    echo "  port 8000   : NOT LISTENING"
fi

echo ""
echo "=== public URL ==="
URL="https://${NGROK_DOMAIN}"
echo "  $URL"
echo "  callback    : $URL/wechat/callback"
HTTP=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$URL/" 2>/dev/null || echo "000")
echo "  health      : HTTP $HTTP"

echo ""
echo "=== uvicorn log (last 5 lines) ==="
if [ -f "$DATA_DIR/uvicorn.log" ]; then
    tail -5 "$DATA_DIR/uvicorn.log" 2>/dev/null || echo "  (empty)"
fi

echo ""
echo "=== ngrok log (last 5 lines) ==="
if [ -f "$DATA_DIR/ngrok.log" ]; then
    tail -5 "$DATA_DIR/ngrok.log" 2>/dev/null | grep -oE '"msg":"[^"]+"' | head -5 || echo "  (empty)"
fi