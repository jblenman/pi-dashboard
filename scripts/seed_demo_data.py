"""Populate the database with synthetic speedtest rows for dashboard development.

Lets you build and preview the dashboard before the real collector has gathered
any history (a trend chart needs many points). Safe to run repeatedly.

    python scripts/seed_demo_data.py --hours 48
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as a loose script from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pidash import config, db  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic speedtest data.")
    parser.add_argument("--hours", type=int, default=48, help="Hours of history to generate.")
    parser.add_argument("--interval-min", type=int, default=30, help="Minutes between points.")
    args = parser.parse_args(argv)

    db.init_db()
    now = datetime.now(timezone.utc)
    points = (args.hours * 60) // args.interval_min
    base_down, base_up = 930.0, 41.0  # asymmetric cable (DOCSIS): fast down, modest up

    for i in range(points):
        ts = now - timedelta(minutes=args.interval_min * (points - i))
        # Gentle evening congestion dip + random noise so charts look alive.
        evening = max(0.0, -math.sin((ts.hour - 6) / 24 * 2 * math.pi))
        down = max(50.0, base_down - 220 * evening + random.uniform(-35, 35))
        up = max(5.0, base_up - 8 * evening + random.uniform(-4, 4))
        row = {
            "ts_utc": ts.isoformat(),
            "ping_ms": round(random.uniform(14, 28) + 12 * evening, 2),
            "jitter_ms": round(random.uniform(0.4, 3.0), 2),
            "download_mbps": round(down, 2),
            "upload_mbps": round(up, 2),
            "packet_loss": round(random.uniform(0, 0.8), 2) if random.random() < 0.2 else 0.0,
            "isp": "Demo ISP",
            "server_name": "Demo Server",
            "server_id": 0,
            "result_url": None,
            "raw_json": json.dumps({"demo": True}),
        }
        db.insert_result(row)

    print("Seeded {} synthetic rows over {}h into {}".format(points, args.hours, config.DB_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
