# pi-dashboard

Turn the Raspberry Pi 5 into a single always-on home box that:

1. **Blocks ads network-wide** with Pi-hole (a DNS sinkhole for the whole LAN).
2. **Logs internet speed** on a schedule and tracks trends over time.
3. **Shows it all on the 7" display** as a kiosk dashboard.

Built to be developed on a desktop/dev machine now and deployed to the Pi later.

## Hardware

- Raspberry Pi 5, 8GB
- Official 7" touch display (800x480)
- Active Cooler
- Pi 5 M.2 HAT (+ NVMe SSD, on hand) -- boot/store on SSD instead of microSD
- 27W USB-C PSU
- microSD (on hand) -- for the initial OS flash

## Architecture

One Pi, three cooperating roles plus the display:

| Role | What it does | Runs as |
|------|--------------|---------|
| **Pi-hole** | Network DNS + ad blocking. Owns its own DB; exposes the v6 REST API locally. | Pi-hole's own installer (systemd) |
| **Collector** | `pidash/speedtest_collector.py` -- runs the Ookla CLI, writes one row per test to SQLite. | systemd timer (every 30 min) |
| **Web** | FastAPI app: serves the dashboard + a small JSON API. Reads the speedtest DB; proxies Pi-hole stats (auth handled server-side). | systemd service (uvicorn) |
| **Display** | Chromium in kiosk mode, fullscreen on `http://localhost:8080`, auto-start on boot. | autostart |

Data:
- **Speedtest history** -> local SQLite (`data/pidash.db`), one row per run.
- **Pi-hole stats** -> not copied; read live from Pi-hole's v6 API (`/api/stats/summary`).

## Tech decisions

- **Custom build** (not Grafana / Speedtest-Tracker off-the-shelf) -- a tailored
  800x480 single-screen dashboard fits the small display better, keeps deps light
  on the Pi, and is the "programming" part you wanted. (Off-the-shelf options are
  listed at the bottom if you change your mind.)
- **Python** collector + **FastAPI** backend + **vanilla HTML/CSS/JS** frontend
  (no build step to maintain on the Pi).
- **Ookla `speedtest` CLI** (`--format=json`), not the Python `speedtest-cli` --
  more accurate, official ARM build.
- **SQLite** -- one file, zero services, ideal for this time-series.

## Build plan -- now vs. at home

### Buildable now on a dev machine (transfer later)
- [x] Project scaffold + config
- [x] Speedtest collector + SQLite layer
- [x] Demo-data seeder (build the dashboard before real history exists)
- [x] FastAPI dashboard: speedtest panel (reads the DB)
- [x] Pi-hole v6 API client + dashboard panel (built against the documented API; mock now, live on deploy)
- [x] systemd units + Chromium kiosk autostart + deploy-over-SSH script (`deploy/`, see `deploy/README.md`)

### At home (needs the Pi / physical access)
- [ ] Flash Raspberry Pi OS (microSD), boot, enable SSH
- [ ] Move root to the NVMe SSD via the M.2 HAT (optional -- you have the SSD)
- [ ] Attach + configure the 7" display
- [ ] Install Pi-hole; set an **App Password** (Settings -> API); point the router's DNS at the Pi
- [ ] Deploy this repo; enable the systemd services; set the kiosk autostart
- [ ] Verify end-to-end on the display

### Later / nice-to-have
- [ ] **3D-printed case** (Bambu Lab A1) -- functional *and* a showpiece. Design constraints:
  integrate the 7" display as a front panel at a viewing angle; clear airflow path for the
  Active Cooler; cutouts for USB-C power, USB/Ethernet, and the M.2 HAT/NVMe; access to the
  microSD slot; GPIO/camera passthrough optional. Start from a known-good Pi 5 + official
  7" display case on MakerWorld and remix, or model from scratch in CadQuery for
  fully parametric parts.

## Running the collector now (dev machine)

Install the Ookla CLI once:

```
winget install Ookla.Speedtest.CLI
```

Run a test and store it (use `py` on Windows; `python3` on the Pi/macOS):

```
py -m pidash.speedtest_collector            # real test -> DB
py -m pidash.speedtest_collector --dry-run  # real test, print only
```

Seed synthetic history for dashboard work (no CLI needed):

```
py scripts/seed_demo_data.py --hours 48
```

## Pi-hole v6 API notes (verified Jun 2026)

- v6 replaced the old `admin/api.php` with a REST API embedded in `pihole-FTL`
  (current: FTL v6.5 / Web v6.4.1 / Core v6.4.x).
- Auth: `POST /api/auth` with the app password -> returns a session id (`sid`)
  -> send it in the `X-FTL-SID` header on later calls. Sessions expire after
  inactivity and each request extends them.
- Generate the app password in the UI: **Settings -> API -> App Password**
  (works alongside 2FA).
- Summary stats: `GET /api/stats/summary`. Full live docs are self-hosted by your
  own Pi-hole at `http://pi.hole/api/docs`.

## Off-the-shelf alternatives (if you'd rather assemble than build)

- **Speedtest Tracker** (self-hosted) -- logging + charts done for you.
- **Grafana + InfluxDB** + a speedtest writer & Pi-hole exporter -- the heavyweight homelab route.
- **Homepage / Dashy** -- dashboard aggregators that can tile Pi-hole + other widgets.

## License

MIT -- see [LICENSE](LICENSE).
