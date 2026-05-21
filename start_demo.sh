#!/usr/bin/env sh
set -eu

export WX_DISPATCH_PORT="${WX_DISPATCH_PORT:-18765}"
export WX_DISPATCH_HOST="${WX_DISPATCH_HOST:-127.0.0.1}"
export WX_DISPATCH_DEMO_MODE="${WX_DISPATCH_DEMO_MODE:-true}"
export WX_DISPATCH_RESET_DEMO_ON_START="${WX_DISPATCH_RESET_DEMO_ON_START:-false}"
export WX_DISPATCH_BASE_URL="${WX_DISPATCH_BASE_URL:-http://${WX_DISPATCH_HOST}:${WX_DISPATCH_PORT}}"

echo "[WX Dispatch] Resetting demo database..."
python scripts/reset_demo_db.py

echo "[WX Dispatch] Starting backend..."
echo "Dashboard:"
echo "${WX_DISPATCH_BASE_URL}/dashboard"
echo "React Admin Console:"
echo "http://127.0.0.1:5173"
echo
echo "WeChat MiniApp API address:"
echo "http://你的局域网IP:${WX_DISPATCH_PORT}"
echo "Replace 你的局域网IP with this computer's LAN IP for real device preview."
echo
echo "Login accounts:"
echo "admin / admin123"
echo "dispatcher / dispatcher123"
echo "driver_demo is driver role and cannot login to admin console."
echo

if command -v open >/dev/null 2>&1; then
  open "${WX_DISPATCH_BASE_URL}/dashboard" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "${WX_DISPATCH_BASE_URL}/dashboard" || true
fi

python backend/main.py
