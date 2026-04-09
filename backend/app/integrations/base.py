"""Base provider protocols for external integrations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.integrations.health import ProviderHealth


@runtime_checkable
class TelematicsProvider(Protocol):
    def fetch_gps_window(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]: ...

    def fetch_eld_window(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]: ...

    def fetch_vehicle_state(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]: ...


@runtime_checkable
class SafetyEventsProvider(Protocol):
    def fetch_safety_events(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]: ...


@runtime_checkable
class DashcamProvider(Protocol):
    def request_clip(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> str: ...

    def fetch_clip_status(self, clip_request_id: str) -> dict[str, Any]: ...

    def download_clip(self, clip_request_id: str) -> bytes | None: ...


@runtime_checkable
class MessagingProvider(Protocol):
    def send_sms(self, to: str, message: str) -> str: ...

    def lookup_delivery_status(self, message_id: str) -> str | None: ...


@runtime_checkable
class VerifyProvider(Protocol):
    def start_verification(self, phone_e164: str) -> str: ...

    def check_verification(self, phone_e164: str, otp: str) -> bool: ...


@runtime_checkable
class VoiceProvider(Protocol):
    def place_call(self, to: str, twiml_content: str) -> str: ...

    def build_voice_twiml(self, message: str) -> str: ...


@runtime_checkable
class StorageProvider(Protocol):
    def file_store(self, key: str, content: bytes, content_type: str | None = None) -> str: ...

    def file_presign(self, key: str, expires_seconds: int = 300) -> str: ...


@runtime_checkable
class FleetDirectoryProvider(Protocol):
    def lookup_vehicle(self, vehicle_id: str) -> dict[str, Any] | None: ...

    def lookup_driver(self, driver_id: str) -> dict[str, Any] | None: ...


@runtime_checkable
class HealthcheckProvider(Protocol):
    def health(self) -> ProviderHealth: ...
