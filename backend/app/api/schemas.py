"""Pydantic request / response schemas for the API."""

import uuid
from typing import Optional

from pydantic import BaseModel


# ── Auth ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "safety_manager"
    org_name: str = "Default"


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    org_id: uuid.UUID
    access_token: str


class MeResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    org_ids: list[uuid.UUID] = []


class LogoutResponse(BaseModel):
    detail: str = "Logged out"


# ── Incidents ───────────────────────────────────────────────────────

class CreateIncidentRequest(BaseModel):
    severity: str
    adc_vehicle_id: str
    samsara_vehicle_id: str
    adc_driver_id: str
    window_start: Optional[str] = None
    window_end: Optional[str] = None


class CreateIncidentResponse(BaseModel):
    incident_id: uuid.UUID
    status: str


class ArtifactSummary(BaseModel):
    artifact_id: uuid.UUID
    artifact_type: str
    status: str
    captured_at_utc: Optional[str] = None
    unavailable_reason: Optional[str] = None


class ExportSummary(BaseModel):
    export_id: uuid.UUID
    status: str
    created_at_utc: Optional[str] = None


class EventSummary(BaseModel):
    event_type: str
    occurred_at_utc: str
    actor_type: str
    payload: Optional[dict] = None


class IncidentListItem(BaseModel):
    incident_id: uuid.UUID
    status: str
    severity: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    samsara_vehicle_id: Optional[str] = None
    adc_driver_id: Optional[str] = None
    created_at_utc: Optional[str] = None
    evidence_captured: int = 0
    evidence_total: int = 0


class IncidentDetailResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    severity: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    samsara_vehicle_id: Optional[str] = None
    adc_driver_id: Optional[str] = None
    created_at_utc: Optional[str] = None
    evidence_inventory: list[ArtifactSummary] = []
    export_status: list[ExportSummary] = []
    timeline: list[EventSummary] = []


# ── Exports ─────────────────────────────────────────────────────────

class CreateExportResponse(BaseModel):
    export_id: uuid.UUID
    status: str


class DownloadExportResponse(BaseModel):
    export_id: uuid.UUID
    url: str
    status: str
