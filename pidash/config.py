"""Central configuration for pi-dashboard.

Defaults target the Raspberry Pi deployment, but every value can be overridden
with an environment variable so the exact same code runs on a dev machine during
development and on the Pi in production.
"""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
BASE_DIR = PACKAGE_DIR.parent

# --- Storage ----------------------------------------------------------------
# SQLite database holding speedtest history. On the Pi this can live on the
# NVMe SSD; during dev it sits in the project's data/ dir.
DB_PATH = Path(os.environ.get("PIDASH_DB", str(BASE_DIR / "data" / "pidash.db")))

# --- Speedtest collector ----------------------------------------------------
# Path to the Ookla speedtest binary. On the Pi (Ookla apt repo) and on Windows
# (after `winget install Ookla.Speedtest.CLI`) it is on PATH as "speedtest".
SPEEDTEST_BIN = os.environ.get("PIDASH_SPEEDTEST_BIN", "speedtest")
# Optional fixed server id; leave unset to let Ookla auto-pick the best server.
SPEEDTEST_SERVER_ID = os.environ.get("PIDASH_SPEEDTEST_SERVER_ID")

# --- Pi-hole (v6 REST API) --------------------------------------------------
# Base URL of the Pi-hole web/API server. On the Pi itself this is localhost.
PIHOLE_URL = os.environ.get("PIDASH_PIHOLE_URL", "http://127.0.0.1")
# App password from the Pi-hole UI: Settings > API > App Password.
# Never hard-code this; supply it via env / a secret file at deploy time.
PIHOLE_APP_PASSWORD = os.environ.get("PIDASH_PIHOLE_APP_PASSWORD", "")
# IPs to drop from the per-client breakdown: the router's relay address (devices that
# haven't renewed their DHCP lease yet still funnel DNS through it) and localhost/the Pi.
PIHOLE_GATEWAY_IP = os.environ.get("PIDASH_GATEWAY_IP", "192.168.1.1")

# --- Web dashboard ----------------------------------------------------------
WEB_HOST = os.environ.get("PIDASH_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("PIDASH_WEB_PORT", "8080"))
