"""Minimal client for the Pi-hole v6 REST API.

Auth flow (v6): POST /api/auth with the app password -> returns a session id
(`sid`) -> send it as the `X-FTL-SID` header on subsequent calls. The sid is
cached and we re-authenticate once on a 401.

When no app password is configured or Pi-hole is unreachable (e.g. during dev on
a non-Pi machine), get_summary() returns representative MOCK data flagged `"mock": True`
so the dashboard still renders.

NOTE: the /api/stats/summary field mapping below should be confirmed against your
own live docs at http://pi.hole/api/docs when you deploy.
"""

import threading
from typing import Optional

import httpx

from pidash import config

_MOCK_SUMMARY = {
    "queries_today": 18342,
    "blocked_today": 4127,
    "percent_blocked": 22.5,
    "domains_blocked": 146238,
    "status": "active",
    "mock": True,
}

_MOCK_BREAKDOWN = {
    "clients": [
        {"label": "desktop", "ip": "192.168.1.20", "count": 4821},
        {"label": "phone", "ip": "192.168.1.31", "count": 3102},
        {"label": "tv", "ip": "192.168.1.44", "count": 1890},
        {"label": "laptop", "ip": "192.168.1.27", "count": 1455},
        {"label": "tablet", "ip": "192.168.1.55", "count": 980},
    ],
    "blocked_domains": [
        {"label": "ads.example.net", "count": 1203},
        {"label": "telemetry.example.com", "count": 877},
        {"label": "tracker.example.io", "count": 654},
        {"label": "metrics.example.org", "count": 432},
        {"label": "beacon.example.net", "count": 311},
    ],
    "mock": True,
}


class PiholeClient:
    def __init__(self, base_url: Optional[str] = None,
                 app_password: Optional[str] = None, timeout: float = 4.0):
        self.base_url = (base_url or config.PIHOLE_URL).rstrip("/")
        self.app_password = app_password if app_password is not None else config.PIHOLE_APP_PASSWORD
        self.timeout = timeout
        self._sid: Optional[str] = None
        self._lock = threading.Lock()

    def _authenticate(self, client: httpx.Client) -> None:
        resp = client.post(self.base_url + "/api/auth", json={"password": self.app_password})
        resp.raise_for_status()
        # v6 shape: {"session": {"valid": true, "sid": "...", ...}}
        self._sid = (resp.json().get("session") or {}).get("sid")

    def _get(self, client: httpx.Client, path: str) -> dict:
        """GET an API path with the cached sid, re-authenticating once on a 401."""
        if not self._sid:
            self._authenticate(client)
        headers = {"X-FTL-SID": self._sid} if self._sid else {}
        resp = client.get(self.base_url + path, headers=headers)
        if resp.status_code == 401:  # session expired -> re-auth once
            self._authenticate(client)
            headers = {"X-FTL-SID": self._sid} if self._sid else {}
            resp = client.get(self.base_url + path, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def _fetch_summary(self, client: httpx.Client) -> dict:
        return self._get(client, "/api/stats/summary")

    def get_summary(self) -> dict:
        """Return normalized Pi-hole stats, or mock data if unavailable."""
        if not self.app_password:
            return dict(_MOCK_SUMMARY)
        try:
            with self._lock, httpx.Client(timeout=self.timeout, verify=False) as client:
                raw = self._fetch_summary(client)
        except Exception:
            return dict(_MOCK_SUMMARY)
        return self._normalize(raw)

    def get_breakdown(self, count: int = 5) -> dict:
        """Top clients (per-device) + top blocked domains, or mock data if unavailable."""
        if not self.app_password:
            return dict(_MOCK_BREAKDOWN)
        try:
            with self._lock, httpx.Client(timeout=self.timeout, verify=False) as client:
                # fetch a few extra clients since we filter the router relay + localhost
                clients_raw = self._get(client, f"/api/stats/top_clients?count={count + 6}")
                blocked_raw = self._get(client, f"/api/stats/top_domains?blocked=true&count={count}")
        except Exception:
            return dict(_MOCK_BREAKDOWN)
        return self._normalize_breakdown(clients_raw, blocked_raw, count)

    @staticmethod
    def _normalize(raw: dict) -> dict:
        q = raw.get("queries", {})
        gravity = raw.get("gravity", {})
        return {
            "queries_today": q.get("total"),
            "blocked_today": q.get("blocked"),
            "percent_blocked": round(q.get("percent_blocked") or 0, 1),
            "domains_blocked": gravity.get("domains_being_blocked"),
            "status": "active",
            "mock": False,
        }

    @staticmethod
    def _normalize_breakdown(clients_raw: dict, blocked_raw: dict, count: int) -> dict:
        skip = {config.PIHOLE_GATEWAY_IP, "127.0.0.1", "::1"}
        clients = []
        for c in clients_raw.get("clients", []):
            ip = c.get("ip", "")
            if ip in skip:
                continue
            # prefer a hostname, strip the .lan suffix; fall back to the IP
            name = (c.get("name") or "").rsplit(".lan", 1)[0] or ip
            clients.append({"label": name, "ip": ip, "count": c.get("count") or 0})
            if len(clients) >= count:
                break
        domains = [
            {"label": d.get("domain", ""), "count": d.get("count") or 0}
            for d in blocked_raw.get("domains", [])[:count]
        ]
        return {"clients": clients, "blocked_domains": domains, "mock": False}
