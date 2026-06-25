#!/usr/bin/env bash
# Install / refresh pi-dashboard on this Raspberry Pi. Idempotent -- safe to re-run.
# Run ON the Pi as your normal user (NOT root):  bash deploy/install.sh
set -euo pipefail

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  echo "Run this as your normal user, not root (it will sudo only where needed)." >&2
  exit 1
fi

PIDASH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDASH_USER="$USER"
echo ">> pi-dashboard: $PIDASH_DIR  (user: $PIDASH_USER)"

# --- Python venv + deps ---
if [ ! -x "$PIDASH_DIR/.venv/bin/python" ]; then
  echo ">> creating venv"
  python3 -m venv "$PIDASH_DIR/.venv"
fi
"$PIDASH_DIR/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"$PIDASH_DIR/.venv/bin/python" -m pip install -r "$PIDASH_DIR/requirements.txt"

# --- Ookla speedtest CLI (not auto-installed; it needs the Ookla apt repo) ---
if ! command -v speedtest >/dev/null 2>&1; then
  echo "!! Ookla 'speedtest' CLI not found. Install it, then re-run:"
  echo "   curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash"
  echo "   sudo apt-get install -y speedtest"
fi

# --- secrets file ---
if [ ! -f "$PIDASH_DIR/deploy/secrets.env" ]; then
  cp "$PIDASH_DIR/deploy/secrets.env.example" "$PIDASH_DIR/deploy/secrets.env"
  echo ">> created deploy/secrets.env -- edit it to add the Pi-hole app password"
fi

# --- systemd units (web service + speedtest timer) ---
echo ">> installing systemd units (will sudo)"
render() { sed -e "s|__PIDASH_DIR__|$PIDASH_DIR|g" -e "s|__PIDASH_USER__|$PIDASH_USER|g" "$1"; }
for unit in pidash-web.service pidash-speedtest.service pidash-speedtest.timer; do
  render "$PIDASH_DIR/deploy/systemd/$unit" | sudo tee "/etc/systemd/system/$unit" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now pidash-web.service
sudo systemctl enable --now pidash-speedtest.timer
sudo systemctl start pidash-speedtest.service || true   # seed one result now

# --- kiosk autostart ---
echo ">> installing kiosk autostart"
chmod +x "$PIDASH_DIR/deploy/kiosk/pidash-kiosk.sh"
# XDG autostart (X11/LXDE and compositors that honor it)
mkdir -p "$HOME/.config/autostart"
sed "s|__PIDASH_DIR__|$PIDASH_DIR|g" "$PIDASH_DIR/deploy/kiosk/pidash-kiosk.desktop" \
  > "$HOME/.config/autostart/pidash-kiosk.desktop"
# labwc (Raspberry Pi OS Bookworm Wayland default) reads its own autostart script
if [ -d "$HOME/.config/labwc" ] || [ "${XDG_SESSION_DESKTOP:-}" = "labwc" ]; then
  mkdir -p "$HOME/.config/labwc"
  touch "$HOME/.config/labwc/autostart"
  LINE="$PIDASH_DIR/deploy/kiosk/pidash-kiosk.sh &"
  grep -qF "$LINE" "$HOME/.config/labwc/autostart" || echo "$LINE" >> "$HOME/.config/labwc/autostart"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo ">> Done. Dashboard: http://${IP:-localhost}:8080"
echo "   - Add the Pi-hole app password to deploy/secrets.env, then: sudo systemctl restart pidash-web"
echo "   - Kiosk launches on next desktop login/reboot. Test now:  deploy/kiosk/pidash-kiosk.sh"
echo "   - Status:  systemctl status pidash-web ; systemctl list-timers pidash-speedtest.timer"
