"""Samsara provider adapter."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import settings


class SamsaraProvider:
    """Capability adapter over Samsara APIs (telematics + dashcam)."""

    BASE_URL = "https://api.samsara.com/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.SAMSARA_API_KEY
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self._clip_requests: dict[str, dict[str, str | None]] = {}

    def _get_json_data(self, path: str, params: Mapping[str, str]) -> list[dict[str, Any]]:
        with httpx.Client() as client:
            resp = client.get(
                f"{self.BASE_URL}/{path}",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    def _window_params(self, start: str | None = None, end: str | None = None) -> dict[str, str]:
        params: dict[str, str] = {}
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        return params

    def fetch_gps_window(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._get_json_data("fleet/vehicles/locations", self._window_params(start, end))

    def fetch_eld_window(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._get_json_data("fleet/drivers/eld", self._window_params(start, end))

    def fetch_vehicle_state(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._get_json_data("fleet/vehicles/stats", self._window_params(start, end))

    def fetch_safety_events(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._get_json_data(
            "fleet/vehicles/safety/events", self._window_params(start, end)
        )

    def request_clip(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        fingerprint = f"{stream}|{start}|{end}".encode()
        clip_id = hashlib.sha256(fingerprint).hexdigest()
        self._clip_requests[clip_id] = {"stream": stream, "start": start, "end": end}
        return clip_id

    def fetch_clip_status(self, clip_request_id: str) -> dict[str, Any]:
        if clip_request_id not in self._clip_requests:
            return {"status": "not_found"}
        return {"status": "ready", "clip_request_id": clip_request_id}

    def download_clip(self, clip_request_id: str) -> bytes | None:
        request = self._clip_requests.get(clip_request_id)
        if not request:
            return None

        params: dict[str, str] = {"stream": request["stream"] or "road_facing"}
        if request.get("start"):
            params["startTime"] = str(request["start"])
        if request.get("end"):
            params["endTime"] = str(request["end"])

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
