#!/usr/bin/env bash
# Launch Chromium in kiosk mode showing the local dashboard.
# Invoked by the autostart entry; can also be run manually to test.
set -uo pipefail

URL="${PIDASH_KIOSK_URL:-http://localhost:8080}"

CHROME="$(command -v chromium-browser || command -v chromium || true)"
if [ -z "$CHROME" ]; then
  echo "chromium not found. Install with: sudo apt install -y chromium-browser" >&2
  exit 1
fi

# Best-effort: disable screen blanking / DPMS under X11 (no-ops under Wayland).
if [ "${XDG_SESSION_TYPE:-}" = "x11" ]; then
  xset s off     2>/dev/null || true
  xset -dpms     2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi

# Wait until the dashboard answers before opening the browser.
for _ in $(seq 1 30); do
  if curl -fsS "$URL/api/speedtest/latest" >/dev/null 2>&1; then break; fi
  sleep 1
done

exec "$CHROME" \
  --kiosk \
  --app="$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --hide-scrollbars \
  --password-store=basic \
  --incognito
