"""Backwards-compatible Samsara client wrapper over integration providers."""

from __future__ import annotations

from app.integrations.service import get_dashcam_provider, get_telematics_provider


class SamsaraClient:
    """Legacy facade; delegates to capability providers from the integration registry."""

    async def get_vehicle_locations_async(self):
        return self.get_vehicle_locations()

    async def get_safety_events_async(self):
        return self.get_safety_events()

    def get_vehicle_locations(self, start: str | None = None, end: str | None = None):
        provider = get_telematics_provider()
        return provider.fetch_gps_window(start=start, end=end)

    def get_safety_events(self, start: str | None = None, end: str | None = None):
        provider = get_telematics_provider()
        fetcher = getattr(provider, "fetch_safety_events", None)
        if fetcher is None:
            return []
        return fetcher(start=start, end=end)

    def get_eld_logs(self, start: str | None = None, end: str | None = None):
        provider = get_telematics_provider()
        return provider.fetch_eld_window(start=start, end=end)

    def get_vehicle_state(self, start: str | None = None, end: str | None = None):
        provider = get_telematics_provider()
        return provider.fetch_vehicle_state(start=start, end=end)

    def fetch_dashcam_stream(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> bytes | None:
        provider = get_dashcam_provider()
        clip_request_id = provider.request_clip(stream=stream, start=start, end=end)
        status = provider.fetch_clip_status(clip_request_id)
        if status.get("status") != "ready":
            return None
        return provider.download_clip(clip_request_id)
