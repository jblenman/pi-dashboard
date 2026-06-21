# Deploying pi-dashboard to the Raspberry Pi

One command from a dev machine pushes the code and configures everything:
the web service, the 30-minute speedtest timer, and the Chromium kiosk.

## What gets installed

| Artifact | Installed as | Purpose |
|----------|--------------|---------|
| `systemd/pidash-web.service` | `/etc/systemd/system/` | uvicorn serving the dashboard on `0.0.0.0:8080`, auto-restart, starts on boot |
| `systemd/pidash-speedtest.service` | `/etc/systemd/system/` | one speedtest run (oneshot) |
| `systemd/pidash-speedtest.timer` | `/etc/systemd/system/` | fires the collector every 30 min (`Persistent=true` catches up after downtime) |
| `kiosk/pidash-kiosk.sh` | run on login | fullscreen Chromium pointed at `localhost:8080` |
| `kiosk/pidash-kiosk.desktop` | `~/.config/autostart/` (+ labwc autostart) | launches the kiosk on desktop login |

The `__PIDASH_DIR__` / `__PIDASH_USER__` placeholders in the unit files are filled
in by `install.sh` at install time, so the project can live anywhere.

## One-time Pi setup

Run once, on the Pi itself (the deploy step below works from any machine).

1. **Flash** Raspberry Pi OS (64-bit) to the microSD with Raspberry Pi Imager.
   In the Imager settings preset the hostname, enable **SSH**, and set the user
   so it boots headless.
2. First boot, then **move the system to the NVMe SSD** via the M.2 HAT if desired
   (Raspberry Pi Imager onto the NVMe, or `rpi-clone`), and set the boot order to NVMe.
3. **Attach the 7" display** (DSI ribbon + power). It comes up at 800x480 -- the
   dashboard is built for exactly that.
4. **Install the Ookla speedtest CLI** (separate apt repo):
   ```
   curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
   sudo apt-get install -y speedtest
   speedtest --accept-license --accept-gdpr   # one-time accept
   ```
5. **Install Pi-hole** and point the router's DNS at the Pi:
   ```
   curl -sSL https://install.pi-hole.net | bash
   ```
   Then in the Pi-hole UI: **Settings > API > App Password** -- generate one and
   keep it for `secrets.env` below. (Pi-hole's installer is interactive, so it's a
   manual step, not part of `install.sh`.)

## Deploy from a dev machine

From a Unix-ish shell (Git Bash or WSL on Windows, or macOS/Linux):
```
deploy/deploy.sh pi@raspberrypi.local
```
This tars the project (minus `.venv/`, `data/`, secrets) over SSH and runs
`install.sh` on the Pi. Re-run any time to push updates -- it's idempotent.

Alternatively, on the Pi directly:
```
git clone <repo> ~/pi-dashboard   # or copy the folder over
cd ~/pi-dashboard && bash deploy/install.sh
```

## Wire up Pi-hole stats

```
cp deploy/secrets.env.example deploy/secrets.env
nano deploy/secrets.env          # set PIDASH_PIHOLE_APP_PASSWORD
sudo systemctl restart pidash-web
```
Without a password the Pi-hole panel shows mock data behind a DEMO badge; with it,
the panel goes live. (`secrets.env` is gitignored.)

## Verify

```
systemctl status pidash-web
systemctl list-timers pidash-speedtest.timer
curl -s localhost:8080/api/speedtest/latest
journalctl -u pidash-web -e          # logs if the page won't load
```
Browse to `http://<pi-ip>:8080` from any device on the LAN.

## Kiosk notes (X11 vs Wayland)

Raspberry Pi OS **Bookworm** defaults to Wayland (**labwc**); older images use X11/LXDE.
`install.sh` covers both: it drops an XDG autostart `.desktop` *and*, if labwc is
present, appends the launch line to `~/.config/labwc/autostart`. If the kiosk doesn't
appear on boot:
- **labwc:** confirm `~/.config/labwc/autostart` has the `pidash-kiosk.sh &` line.
- **wayfire:** add `pidash-kiosk = /home/<user>/pi-dashboard/deploy/kiosk/pidash-kiosk.sh`
  under `[autostart]` in `~/.config/wayfire.ini`.
- **X11/LXDE:** the `~/.config/autostart/pidash-kiosk.desktop` entry is honored.
- Test the launcher by hand any time: `deploy/kiosk/pidash-kiosk.sh`.

## Troubleshooting

- **`bad interpreter: /usr/bin/env bash^M`** -- the scripts arrived with Windows line
  endings. Fix: `sed -i 's/\r$//' deploy/*.sh deploy/kiosk/*.sh` (deploy.sh does this
  automatically; the `.gitattributes` keeps git checkouts LF).
- **Port 8080 in use / not reachable** -- check `systemctl status pidash-web`; Pi-hole
  uses 80/443, so there's no conflict with 8080.
- **No speedtest data** -- `systemctl start pidash-speedtest.service` then read
  `journalctl -u pidash-speedtest -e`; make sure the Ookla CLI is installed and licensed.
