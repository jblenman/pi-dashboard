"""Run an Ookla speedtest and append the result to the database.

Designed to be invoked on a schedule (a systemd timer on the Pi; Task Scheduler
or a manual run on a dev machine). Prints one compact JSON line summarizing the run.

    python -m pidash.speedtest_collector             # run a real test -> DB
    python -m pidash.speedtest_collector --dry-run   # run a real test, print only

Requires the Ookla `speedtest` CLI (NOT the Python `speedtest-cli` package):
    Raspberry Pi:  curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
                   sudo apt-get install speedtest
    Windows (dev): winget install Ookla.Speedtest.CLI
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

from pidash import config, db


def run_speedtest() -> dict:
    """Invoke the Ookla CLI and return the parsed JSON payload."""
    cmd = [
        config.SPEEDTEST_BIN,
        "--format=json",
        "--accept-license",
        "--accept-gdpr",
    ]
    if config.SPEEDTEST_SERVER_ID:
        cmd += ["--server-id", str(config.SPEEDTEST_SERVER_ID)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError("speedtest failed (exit {}): {}".format(proc.returncode, detail))
    return json.loads(proc.stdout)


def parse_payload(payload: dict) -> dict:
    """Flatten the Ookla JSON into a DB row.

    Ookla reports bandwidth in BYTES per second; convert to Mbps (decimal mega).
    """
    def mbps(node):
        bw = (node or {}).get("bandwidth")
        return round(bw * 8 / 1_000_000, 2) if bw else None

    ping = payload.get("ping", {})
    server = payload.get("server", {})
    result = payload.get("result", {})
    ts = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()

    return {
        "ts_utc": ts,
        "ping_ms": ping.get("latency"),
        "jitter_ms": ping.get("jitter"),
        "download_mbps": mbps(payload.get("download")),
        "upload_mbps": mbps(payload.get("upload")),
        "packet_loss": payload.get("packetLoss"),
        "isp": payload.get("isp"),
        "server_name": server.get("name"),
        "server_id": server.get("id"),
        "result_url": result.get("url"),
        "raw_json": json.dumps(payload, separators=(",", ":")),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a speedtest and log the result.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run the test and print the parsed row, but do not write to the DB.",
    )
    args = parser.parse_args(argv)

    try:
        payload = run_speedtest()
    except FileNotFoundError:
        print(
            "ERROR: speedtest binary not found at '{}'. Install the Ookla CLI "
            "or set PIDASH_SPEEDTEST_BIN.".format(config.SPEEDTEST_BIN),
            file=sys.stderr,
        )
        return 2
    except (RuntimeError, json.JSONDecodeError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1

    row = parse_payload(payload)
    summary = {k: row[k] for k in (
        "ts_utc", "ping_ms", "jitter_ms", "download_mbps", "upload_mbps", "packet_loss",
    )}
    print(json.dumps(summary))

    if not args.dry_run:
        db.init_db()
        db.insert_result(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
