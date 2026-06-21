"""Host system stats for the dashboard's status bar (CPU temp, load, memory, uptime).

Real values come from Linux's /sys and /proc, so they populate on the Pi. On a
non-Linux dev machine (e.g. Windows) there's no equivalent, so representative
MOCK values are returned flagged `"mock": True` -- same pattern as the Pi-hole client.
"""

import os
import platform


def _read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _cpu_temp_c():
    # Raspberry Pi and most Linux SBCs expose this in millidegrees C.
    v = _read_int("/sys/class/thermal/thermal_zone0/temp")
    return round(v / 1000, 1) if v is not None else None


def _cpu_load_pct():
    # 1-minute load average as a percentage of available cores.
    try:
        load1 = os.getloadavg()[0]
        cores = os.cpu_count() or 1
        return round(min(load1 / cores * 100, 999), 1)
    except (OSError, AttributeError):
        return None


def _mem_used_pct():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])  # kB
        total, avail = info.get("MemTotal"), info.get("MemAvailable")
        if total and avail is not None:
            return round((total - avail) / total * 100, 1)
    except (OSError, ValueError):
        pass
    return None


def _uptime_sec():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError):
        return None


_MOCK = {
    "cpu_temp_c": 47.2,
    "cpu_load_pct": 11.5,
    "mem_used_pct": 34.0,
    "uptime_sec": 275400,  # ~3d 4h
    "mock": True,
}


def get_stats() -> dict:
    """Return host stats, or representative mock data off-Pi (non-Linux)."""
    if platform.system() != "Linux":
        return dict(_MOCK)
    return {
        "cpu_temp_c": _cpu_temp_c(),
        "cpu_load_pct": _cpu_load_pct(),
        "mem_used_pct": _mem_used_pct(),
        "uptime_sec": _uptime_sec(),
        "mock": False,
    }
