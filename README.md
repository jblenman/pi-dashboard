# pi-dashboard

Turn the Raspberry Pi 5 into a single always-on home box that:

1. **Blocks ads network-wide** with Pi-hole (a DNS sinkhole for the whole LAN).
2. **Logs internet speed** on a schedule and tracks trends over time.
3. **Shows it all on the 7" display** as a kiosk dashboard.

The Pi-hole and system panels fall back to mock data when run off-Pi, so the whole
dashboard can be built and previewed on any machine without the hardware.

**Docs:** [`deploy/README.md`](deploy/README.md) to deploy · [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
for routing your network through Pi-hole (incl. Netgear Nighthawk), what happens if the
Pi goes down, and day-to-day upkeep.

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
  800x480 single-screen dashboard fits the small display better and keeps deps light
  on the Pi. (Off-the-shelf options are listed at the bottom.)
- **Python** collector + **FastAPI** backend + **vanilla HTML/CSS/JS** frontend
  (no build step to maintain on the Pi).
- **Ookla `speedtest` CLI** (`--format=json`), not the Python `speedtest-cli` --
  more accurate, official ARM build.
- **SQLite** -- one file, zero services, ideal for this time-series.

## Status

Done:
- [x] Config, SQLite layer, and the Ookla speedtest collector
- [x] Demo-data seeder (preview the dashboard before real history exists)
- [x] FastAPI backend + 800x480 UI -- speedtest panel, Pi-hole panel, system status bar
- [x] Pi-hole v6 API client (representative mock data until a Pi-hole is reachable)
- [x] Deploy: systemd units, Chromium kiosk autostart, deploy-over-SSH script (`deploy/`)

Remaining:
- [ ] Hardware bring-up: flash Raspberry Pi OS, optional NVMe boot via the M.2 HAT, attach the
  7" display, install Pi-hole and set an **App Password**, point the router's DNS at the Pi, then
  deploy (`deploy/deploy.sh` -- full steps in [`deploy/README.md`](deploy/README.md))
- [ ] **3D-printed case** (Bambu Lab A1) -- functional *and* a showpiece: the 7" display as an
  angled front panel, clear airflow for the Active Cooler, cutouts for USB-C power, USB/Ethernet,
  and the M.2 HAT/NVMe, plus microSD access. Remix a known-good Pi 5 + 7" display case on
  MakerWorld, or model it from scratch in CadQuery.

## Running the collector locally

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
