"""FastAPI app: serves the kiosk dashboard and its JSON API.

Run (from the project root, with it on PYTHONPATH):
    py -m uvicorn web.app:app --host 127.0.0.1 --port 8080
On the Pi this is launched by a systemd service bound to 0.0.0.0.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pidash import db
from pidash.pihole_client import PiholeClient
from pidash.system_stats import get_stats as get_system_stats

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="pi-dashboard")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_pihole = PiholeClient()


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/speedtest/latest")
def speedtest_latest():
    row = db.latest_result()
    if not row:
        return JSONResponse({})
    return JSONResponse({
        "ts": row["ts_utc"],
        "download": row["download_mbps"],
        "upload": row["upload_mbps"],
        "ping": row["ping_ms"],
        "jitter": row["jitter_ms"],
        "packet_loss": row["packet_loss"],
        "isp": row["isp"],
        "server": row["server_name"],
    })


@app.get("/api/speedtest/history")
def speedtest_history(limit: int = 96):
    rows = db.recent_results(limit)
    return JSONResponse([
        {"ts": r["ts_utc"], "download": r["download_mbps"],
         "upload": r["upload_mbps"], "ping": r["ping_ms"]}
        for r in rows
    ])


@app.get("/api/pihole/summary")
def pihole_summary():
    return JSONResponse(_pihole.get_summary())


@app.get("/api/pihole/breakdown")
def pihole_breakdown():
    """Top clients (per-device) and top blocked domains for the lower panels."""
    return JSONResponse(_pihole.get_breakdown())


@app.get("/api/speedtest/stats")
def speedtest_stats():
    """Aggregate speedtest stats over the last 24h and 7d."""
    def shape(s):
        n = (s or {}).get("n") or 0
        if not n:
            return {"n": 0}
        rnd = lambda v: round(v, 1) if v is not None else None
        return {
            "n": n,
            "dl_avg": rnd(s["dl_avg"]), "dl_min": rnd(s["dl_min"]), "dl_max": rnd(s["dl_max"]),
            "ul_avg": rnd(s["ul_avg"]), "ul_min": rnd(s["ul_min"]), "ul_max": rnd(s["ul_max"]),
            "ping_avg": rnd(s["ping_avg"]), "ping_min": rnd(s["ping_min"]),
        }
    return JSONResponse({"day": shape(db.stats(24)), "week": shape(db.stats(24 * 7))})


@app.get("/api/system")
def system_stats():
    return JSONResponse(get_system_stats())
