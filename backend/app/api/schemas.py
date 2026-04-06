"""Pydantic request / response schemas for the API."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

EmailStrLike = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=6,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    ),
]
PhoneE164 = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^\+[1-9]\d{1,14}$",
    ),
]
OtpCode = Annotated[str, StringConstraints(pattern=r"^\d{4,8}$")]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
LongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
VehicleId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]
DriverId = VehicleId
QrToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=8, max_length=256, pattern=r"^[A-Za-z0-9_-]+$"
    ),
]

UserRole = Literal["admin", "safety_manager"]
InstructionScope = Literal["default", "company", "insurer"]
IncidentSeverity = Literal["minor", "serious", "critical"]
IncidentStatus = Literal["open", "evidence_capturing", "closed"]
ArtifactStatus = Literal["pending", "captured", "unavailable"]
ExportStatus = Literal["requested", "processing", "ready", "failed"]
VehicleStrategy = Literal["qr", "last_assigned"]
CaptureState = Literal[
    "failed", "complete", "in_progress", "requested", "lockdown", "closed", "pending"
]
ArtifactUploadContentType = Literal[
    "application/pdf",
    "image/jpeg",
    "image/png",
    "video/mp4",
]
DriverTimelineEventName = Literal[
    "driver_protocol_launch_confirmed",
    "driver_safety_gate_viewed",
    "driver_safety_gate_acknowledged",
    "driver_instruction_step_viewed",
    "driver_instruction_step_acknowledged",
    "driver_scene_facts_saved",
    "driver_parties_saved",
    "driver_media_uploaded",
    "driver_media_upload_failed",
    "driver_narrative_saved",
    "driver_report_submitted",
]


# ── Auth ────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: EmailStrLike
    password: Annotated[str, StringConstraints(min_length=4, max_length=256)]


class RequestOtpRequest(BaseModel):
    phone_e164: PhoneE164 = Field(
        description="Phone number in E.164 format, e.g. +15551234567.",
    )


class LoginResponse(BaseModel):
    access_token: Annotated[str, StringConstraints(min_length=16)]
    token_type: Literal["bearer"] = "bearer"
    role: UserRole


class RegisterRequest(BaseModel):
    email: EmailStrLike
    password: Annotated[str, StringConstraints(min_length=4, max_length=256)]
    role: UserRole = "safety_manager"
    org_name: ShortText = "Default"


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStrLike
    role: UserRole
    org_id: uuid.UUID
    access_token: Annotated[str, StringConstraints(min_length=16)]


class MeResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStrLike
    role: UserRole
    org_ids: list[uuid.UUID] = Field(default_factory=list)
    active_org_id: Optional[uuid.UUID] = None


class LogoutResponse(BaseModel):
    detail: str = "Logged out"


# ── Incidents ───────────────────────────────────────────────────────


class CreateIncidentRequest(BaseModel):
    severity: IncidentSeverity
    adc_vehicle_id: VehicleId
    samsara_vehicle_id: VehicleId
    adc_driver_id: DriverId
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class CreateIncidentResponse(BaseModel):
    incident_id: uuid.UUID
    status: IncidentStatus


class ArtifactSummary(BaseModel):
    artifact_id: uuid.UUID
    artifact_type: ShortText
    status: ArtifactStatus
    captured_at_utc: Optional[datetime] = None
    unavailable_reason: Optional[ShortText] = None


class ExportSummary(BaseModel):
    export_id: uuid.UUID
    status: ExportStatus
    created_at_utc: Optional[datetime] = None


class EventSummary(BaseModel):
    event_type: ShortText
    occurred_at_utc: datetime
    actor_type: ShortText
    payload: Optional[dict] = None


class IncidentListItem(BaseModel):
    incident_id: uuid.UUID
    status: IncidentStatus
    severity: Optional[IncidentSeverity] = None
    adc_vehicle_id: Optional[VehicleId] = None
    samsara_vehicle_id: Optional[VehicleId] = None
    adc_driver_id: Optional[DriverId] = None
    created_at_utc: Optional[datetime] = None
    evidence_captured: int = Field(default=0, ge=0)
    evidence_total: int = Field(default=0, ge=0)


class IncidentDetailResponse(BaseModel):
    incident_id: uuid.UUID
    status: IncidentStatus
    severity: Optional[IncidentSeverity] = None
    adc_vehicle_id: Optional[VehicleId] = None
    samsara_vehicle_id: Optional[VehicleId] = None
    adc_driver_id: Optional[DriverId] = None
    created_at_utc: Optional[datetime] = None
    evidence_inventory: list[ArtifactSummary] = Field(default_factory=list)
    export_status: list[ExportSummary] = Field(default_factory=list)
    timeline: list[EventSummary] = Field(default_factory=list)


# ── Exports ─────────────────────────────────────────────────────────


class CreateExportResponse(BaseModel):
    export_id: uuid.UUID
    status: ExportStatus


class DownloadExportResponse(BaseModel):
    export_id: uuid.UUID
    url: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    status: ExportStatus


# ── Driver ──────────────────────────────────────────────────────────


class VehicleInfo(BaseModel):
    adc_vehicle_id: VehicleId
    display_label: ShortText


class DriverMeResponse(BaseModel):
    driver_id: uuid.UUID
    org_id: uuid.UUID
    phone_e164: PhoneE164
    display_name: ShortText
    vehicle: Optional[VehicleInfo] = None


class DriverOtpRequest(BaseModel):
    phone_e164: PhoneE164


class DriverOtpRequestResponse(BaseModel):
    detail: str = "OTP sent"


class DriverOtpVerifyRequest(BaseModel):
    phone_e164: PhoneE164
    otp_code: OtpCode


class DriverOtpVerifyResponse(BaseModel):
    access_token: Annotated[str, StringConstraints(min_length=16)]
    token_type: Literal["bearer"] = "bearer"


class ResolveQrRequest(BaseModel):
    qr_token: QrToken


class ResolveQrResponse(BaseModel):
    adc_vehicle_id: VehicleId
    display_label: ShortText


class DriverArtifactUploadUrlRequest(BaseModel):
    artifact_type: ShortText
    content_type: ArtifactUploadContentType
    file_name: Annotated[str, StringConstraints(min_length=1, max_length=255)]


class DriverArtifactUploadUrlResponse(BaseModel):
    artifact_id: uuid.UUID
    upload_url: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    s3_key: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    expires_in_seconds: int = Field(ge=1, le=900)
    content_type: ArtifactUploadContentType


class DriverArtifactCompleteRequest(BaseModel):
    artifact_id: uuid.UUID
    byte_size: int = Field(gt=0)
    sha256: Optional[Annotated[str, StringConstraints(min_length=16, max_length=128)]] = (
        None
    )


class DriverArtifactCompleteResponse(BaseModel):
    artifact_id: uuid.UUID
    status: ArtifactStatus


class DriverArtifactListResponse(BaseModel):
    artifacts: list[ArtifactSummary] = Field(default_factory=list)


# ── Admin driver protocol ─────────────────────────────────────────


class DriverProtocolSettingsRequest(BaseModel):
    instruction_source: InstructionScope
    require_ack: bool
    sms_enabled: bool
    voice_enabled: bool
    safety_manager_phone: Optional[PhoneE164] = None


class DriverProtocolSettingsResponse(DriverProtocolSettingsRequest):
    pass


class DriverInstructionStep(BaseModel):
    step_id: Optional[uuid.UUID] = None
    order: int = Field(ge=1, le=100)
    title: ShortText
    body: LongText
    enabled: bool = True


class DriverInstructionSetRequest(BaseModel):
    scope: InstructionScope
    steps: list[DriverInstructionStep] = Field(min_length=1, max_length=50)


class DriverInstructionStepResponse(BaseModel):
    step_id: uuid.UUID
    step_order: int
    title: ShortText
    body: LongText


class DriverInstructionSetResponse(DriverInstructionSetRequest):
    instruction_set_id: uuid.UUID
    require_ack: Optional[bool] = None
    steps: list[DriverInstructionStep | DriverInstructionStepResponse] = Field(
        default_factory=list
    )
    model_config = ConfigDict(extra="ignore")


# ── Driver incident / instruction responses ────────────────────────


class DriverIncidentInitiateRequest(BaseModel):
    vehicle_strategy: VehicleStrategy
    qr_token: Optional[QrToken] = None
    device_location: Optional[dict] = None
    device: Optional[dict] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class DriverIncidentInitiateResponse(BaseModel):
    incident_id: uuid.UUID
    safety_notified: bool
    capture_started: bool


class DriverActiveIncidentResponse(BaseModel):
    incident_id: uuid.UUID
    status: IncidentStatus
    adc_vehicle_id: Optional[str] = None
    adc_driver_id: Optional[str] = None
    created_at_utc: datetime


class DriverInstructionAckRequest(BaseModel):
    instruction_set_id: uuid.UUID


class DriverInstructionAckResponse(BaseModel):
    acknowledged: bool


class DriverTimelineEventWriteRequest(BaseModel):
    event_name: DriverTimelineEventName
    payload: dict = Field(default_factory=dict)


class DriverTimelineEventWriteResponse(BaseModel):
    acknowledged: bool = True


class DriverIncidentStatusResponse(BaseModel):
    incident_id: uuid.UUID
    status: IncidentStatus
    safety_notified: bool
    capture_state: CaptureState
    adc_vehicle_id: Optional[str] = None
    adc_driver_id: Optional[str] = None
    created_at_utc: datetime
    protocol_started_at_utc: Optional[datetime] = None
    evidence_requested_at_utc: Optional[datetime] = None
    last_evidence_update_utc: Optional[datetime] = None


class DriverIncidentReportScenePatchRequest(BaseModel):
    scene: dict = Field(default_factory=dict)


class DriverIncidentReportPartiesPatchRequest(BaseModel):
    parties: list[dict] = Field(default_factory=list)


class DriverIncidentReportNarrativePatchRequest(BaseModel):
    narrative: LongText


class DriverIncidentReportPatchRequest(BaseModel):
    scene: Optional[dict] = None
    parties: Optional[list[dict]] = None
    narrative: Optional[LongText] = None


class DriverIncidentReportWriteResponse(BaseModel):
    incident_id: uuid.UUID
    updated_sections: list[Literal["scene", "parties", "narrative"]] = Field(
        default_factory=list
    )
    submitted: bool = False


# ── Admin vehicles / QR ────────────────────────────────────────────


class AdminVehicleSummary(BaseModel):
    adc_vehicle_id: VehicleId
    display_label: ShortText


class RotateQrResponse(BaseModel):
    qr_token: QrToken


class QrPayloadResponse(BaseModel):
    deep_link: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
