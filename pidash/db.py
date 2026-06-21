"""SQLite persistence for speedtest history.

One row per speedtest run. Pi-hole stats are deliberately NOT stored here --
Pi-hole keeps its own long-term database and we read it live via its v6 API.
"""

import sqlite3
from typing import List, Optional

from pidash import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS speedtest_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc        TEXT    NOT NULL,            -- ISO-8601 UTC
    ping_ms       REAL,
    jitter_ms     REAL,
    download_mbps REAL,
    upload_mbps   REAL,
    packet_loss   REAL,
    isp           TEXT,
    server_name   TEXT,
    server_id     INTEGER,
    result_url    TEXT,
    raw_json      TEXT                          -- full Ookla payload, for future use
);
CREATE INDEX IF NOT EXISTS idx_speedtest_ts ON speedtest_results (ts_utc);
"""

_COLUMNS = (
    "ts_utc", "ping_ms", "jitter_ms", "download_mbps", "upload_mbps",
    "packet_loss", "isp", "server_name", "server_id", "result_url", "raw_json",
)


def get_connection() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def insert_result(row: dict) -> int:
    placeholders = ", ".join("?" for _ in _COLUMNS)
    values = [row.get(c) for c in _COLUMNS]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO speedtest_results ({cols}) VALUES ({ph})".format(
                cols=", ".join(_COLUMNS), ph=placeholders
            ),
            values,
        )
        return cur.lastrowid


def latest_result() -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM speedtest_results ORDER BY ts_utc DESC LIMIT 1"
        ).fetchone()


def recent_results(limit: int = 96) -> List[sqlite3.Row]:
    """Most recent N rows, returned oldest-first for charting.

    96 points == 48h of history at the default 30-minute cadence.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM speedtest_results ORDER BY ts_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return list(reversed(rows))
