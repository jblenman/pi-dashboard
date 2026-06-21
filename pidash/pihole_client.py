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

    def _fetch_summary(self, client: httpx.Client) -> dict:
        if not self._sid:
            self._authenticate(client)
        headers = {"X-FTL-SID": self._sid} if self._sid else {}
        resp = client.get(self.base_url + "/api/stats/summary", headers=headers)
        if resp.status_code == 401:  # session expired -> re-auth once
            self._authenticate(client)
            headers = {"X-FTL-SID": self._sid} if self._sid else {}
            resp = client.get(self.base_url + "/api/stats/summary", headers=headers)
        resp.raise_for_status()
        return resp.json()

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
