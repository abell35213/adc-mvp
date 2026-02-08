"""Samsara API client."""

import httpx

from app.core.config import settings


class SamsaraClient:
    """Client for interacting with the Samsara API."""

    BASE_URL = "https://api.samsara.com/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.SAMSARA_API_KEY
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    # ── Async helpers (original) ──────────────────────────────────────

    async def get_vehicle_locations_async(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/fleet/vehicles/locations",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_safety_events_async(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/fleet/vehicles/safety/events",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Sync fetchers used by Celery tasks ────────────────────────────

    def get_vehicle_locations(self, start: str | None = None, end: str | None = None):
        """Fetch vehicle GPS locations for the given time window."""
        params = {}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        with httpx.Client() as client:
            resp = client.get(
                f"{self.BASE_URL}/fleet/vehicles/locations",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    def get_safety_events(self, start: str | None = None, end: str | None = None):
        """Fetch safety events for the given time window."""
        params = {}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        with httpx.Client() as client:
            resp = client.get(
                f"{self.BASE_URL}/fleet/vehicles/safety/events",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    def get_eld_logs(self, start: str | None = None, end: str | None = None):
        """Fetch ELD log data for the given time window."""
        params = {}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        with httpx.Client() as client:
            resp = client.get(
                f"{self.BASE_URL}/fleet/drivers/eld",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    def get_vehicle_state(self, start: str | None = None, end: str | None = None):
        """Fetch vehicle state data for the given time window."""
        params = {}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        with httpx.Client() as client:
            resp = client.get(
                f"{self.BASE_URL}/fleet/vehicles/stats",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    def fetch_dashcam_stream(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> bytes | None:
        """Download dashcam video bytes for *stream* within the time window.

        Returns raw video bytes, or None when the stream has no footage.
        """
        params: dict = {"stream": stream}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        with httpx.Client() as client:
            resp = client.get(
                f"{self.BASE_URL}/fleet/vehicles/camera/stream",
                headers=self.headers,
                params=params,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
