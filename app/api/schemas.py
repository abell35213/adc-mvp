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


class ExportSummary(BaseModel):
    export_id: uuid.UUID
    status: str


class IncidentDetailResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    severity: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    samsara_vehicle_id: Optional[str] = None
    adc_driver_id: Optional[str] = None
    evidence_inventory: list[ArtifactSummary] = []
    export_status: list[ExportSummary] = []


# ── Exports ─────────────────────────────────────────────────────────

class CreateExportResponse(BaseModel):
    export_id: uuid.UUID
    status: str


class DownloadExportResponse(BaseModel):
    export_id: uuid.UUID
    url: str
    status: str
