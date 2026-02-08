"""Samsara API client."""

import httpx

from app.core.config import settings


class SamsaraClient:
    """Client for interacting with the Samsara API."""

    BASE_URL = "https://api.samsara.com/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.SAMSARA_API_KEY
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    async def get_vehicle_locations(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/fleet/vehicles/locations",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_safety_events(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/fleet/vehicles/safety/events",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()
