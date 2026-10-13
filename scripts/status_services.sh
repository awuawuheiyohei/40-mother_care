#!/usr/bin/env bash
# Show mother_care service status + current public URL.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$PROJECT_DIR/data"

# ngrok reserved domain — must match deploy/com.mothercare.ngrok.plist
NGROK_DOMAIN="${NGROK_DOMAIN:-matcher-cufflink-penpal.ngrok-free.dev}"

echo "=== launchd status ==="
# Capture once and match with herestrings: piping launchctl into `grep -q` makes
# grep exit early, launchctl takes SIGPIPE, and `set -o pipefail` turns that into
# a false "NOT LOADED" (reproducible for whichever label sorts first).
LAUNCHD_LIST="$(launchctl list)"

for svc in uvicorn ngrok dingtalk; do
    if grep -q "com.mothercare.$svc" <<<"$LAUNCHD_LIST"; then
        PID=$(awk -v label="com.mothercare.$svc" '$3 == label {print $1}' <<<"$LAUNCHD_LIST")
        printf "  %-11s : loaded (pid %s)\n" "$svc" "$PID"
    else
        printf "  %-11s : NOT LOADED\n" "$svc"
    fi
done

if grep -q "com.mothercare.cloudflared" <<<"$LAUNCHD_LIST"; then
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

echo ""
echo "=== dingtalk log (last 5 lines) ==="
if [ -f "$DATA_DIR/dingtalk.log" ]; then
    tail -5 "$DATA_DIR/dingtalk.log" 2>/dev/null || echo "  (empty)"
else
    echo "  (no $DATA_DIR/dingtalk.log)"
fi
