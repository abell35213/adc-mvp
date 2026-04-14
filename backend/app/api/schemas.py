"""Pydantic request / response schemas for the API."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.exports import EXPORT_PROGRESS_STAGES, EXPORT_STATUSES, EXPORT_TYPES
from app.domain.packet_profiles import (
    DEFAULT_PROFILE_BY_EXPORT_TYPE,
    get_default_packet_profile,
    get_packet_profile,
)
from app.security.permissions import ALL_RECOMMENDED_CAPABILITIES, CANONICAL_ROLES, Role

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

UserRole = Literal["system_admin", "org_admin", "safety_manager"]
CapabilityName = Literal[
    "incident:read",
    "incident:write",
    "incident:close",
    "incident:reopen",
    "incident:escalate",
    "export:read",
    "export:write",
    "driver_protocol:read",
    "driver_protocol:write",
    "vehicle_qr:read",
    "vehicle_qr:write",
]
assert set(CANONICAL_ROLES) == {"system_admin", "org_admin", "safety_manager"}
assert set(ALL_RECOMMENDED_CAPABILITIES) == {
    "incident:read",
    "incident:write",
    "incident:close",
    "incident:reopen",
    "incident:escalate",
    "export:read",
    "export:write",
    "driver_protocol:read",
    "driver_protocol:write",
    "vehicle_qr:read",
    "vehicle_qr:write",
}
InstructionScope = Literal["default", "company", "insurer"]
IncidentSeverity = Literal["minor", "serious", "critical"]
IncidentStatus = Literal["open", "evidence_capturing", "closed"]
IncidentCaseStatus = Literal[
    "new",
    "in_review",
    "awaiting_evidence",
    "awaiting_follow_up",
    "ready_for_export",
    "exported",
    "escalated",
    "closed",
]
IncidentQueue = Literal[
    "Unassigned",
    "Safety Review",
    "Claims Review",
    "Escalated",
    "Export Queue",
]
ArtifactStatus = Literal["pending", "captured", "unavailable"]
ExportType = Literal[
    "court_defense", "insurer_packet", "internal_review", "compliance_audit"
]
ExportStatus = Literal[
    "requested", "queued", "processing", "ready", "failed", "expired"
]
ExportProgressStage = Literal[
    "request_accepted",
    "gathering_incident_data",
    "assembling_documents",
    "packaging_evidence",
    "uploading_export",
    "ready_for_download",
]

assert set(EXPORT_TYPES) == {
    "court_defense",
    "insurer_packet",
    "internal_review",
    "compliance_audit",
}
assert set(EXPORT_STATUSES) == {
    "requested",
    "queued",
    "processing",
    "ready",
    "failed",
    "expired",
}
assert set(EXPORT_PROGRESS_STAGES) == {
    "request_accepted",
    "gathering_incident_data",
    "assembling_documents",
    "packaging_evidence",
    "uploading_export",
    "ready_for_download",
}
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


ApiErrorCode = Literal[
    "EXPORT_DELAYED",
    "EXPORT_NOT_READY",
    "EXPORT_EXPIRED",
    "EXPORT_RETRY_ALLOWED",
    "UPLOAD_RETRY_RECOMMENDED",
    "THIRD_PARTY_DEGRADED",
    "RESOURCE_NOT_FOUND",
    "ACCESS_DENIED",
    "RATE_LIMITED",
    "REQUEST_INVALID",
    "INTERNAL_ERROR",
]


class ApiErrorDetail(BaseModel):
    message: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    code: ApiErrorCode
    retry_hint: (
        Annotated[str, StringConstraints(min_length=1, max_length=300)] | None
    ) = None
    correlation_id: (
        Annotated[str, StringConstraints(min_length=8, max_length=128)] | None
    ) = None


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail


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
    mfa_code: OtpCode | None = None


class RequestOtpRequest(BaseModel):
    phone_e164: PhoneE164 = Field(
        description="Phone number in E.164 format, e.g. +15551234567.",
    )


class LoginResponse(BaseModel):
    access_token: Annotated[str, StringConstraints(min_length=16)]
    token_type: Literal["bearer"] = "bearer"
    role: UserRole
    capabilities: list[CapabilityName] = Field(default_factory=list)


class RefreshResponse(BaseModel):
    access_token: Annotated[str, StringConstraints(min_length=16)]
    token_type: Literal["bearer"] = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStrLike
    password: Annotated[str, StringConstraints(min_length=4, max_length=256)]
    role: UserRole = Role.SAFETY_MANAGER.value
    org_name: ShortText = "Default"


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStrLike
    role: UserRole
    capabilities: list[CapabilityName] = Field(default_factory=list)
    org_id: uuid.UUID
    access_token: Annotated[str, StringConstraints(min_length=16)]


class MeResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStrLike
    role: UserRole
    capabilities: list[CapabilityName] = Field(default_factory=list)
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
    unavailable_message: Optional[str] = None


class ExportSummary(BaseModel):
    export_id: uuid.UUID
    incident_id: Optional[uuid.UUID] = None
    export_type: ExportType = "court_defense"
    profile_id: str = "court_defense_v1"
    requested_by_user_id: Optional[uuid.UUID] = None
    retry_parent_export_id: Optional[uuid.UUID] = None
    options_json: dict[str, Any] = Field(default_factory=dict)
    status: ExportStatus
    progress_stage: ExportProgressStage = "request_accepted"
    error_message: Optional[str] = None
    package_sha256: Optional[str] = None
    byte_size: Optional[int] = None
    artifact_count: int = Field(default=0, ge=0)
    timeline_event_count: int = Field(default=0, ge=0)
    requested_at_utc: Optional[datetime] = None
    processing_started_at_utc: Optional[datetime] = None
    completed_at_utc: Optional[datetime] = None
    expires_at_utc: Optional[datetime] = None
    created_at_utc: Optional[datetime] = None
    updated_at_utc: Optional[datetime] = None


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
    completeness_percent: int = Field(default=0, ge=0, le=100)
    completeness_status: str = "incomplete"
    readiness_state: str = "not_ready"
    blocker_counts: dict[str, int] = Field(default_factory=dict)


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
    messaging_reliability: dict[str, int] = Field(default_factory=dict)
    completeness_percent: int = Field(default=0, ge=0, le=100)
    completeness_status: str = "incomplete"
    readiness_state: str = "not_ready"
    completeness_missing_items: list[str] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)


class IncidentStatusPatchRequest(BaseModel):
    case_status: IncidentCaseStatus
    reason: LongText


class IncidentStatusPatchResponse(BaseModel):
    incident_id: uuid.UUID
    case_status: IncidentCaseStatus
    transition_reason: LongText


IncidentOwnerPatchOperation = Literal["assign", "reassign", "clear"]


class IncidentOwnerPatchRequest(BaseModel):
    operation: IncidentOwnerPatchOperation
    owner_user_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation == "clear" and self.owner_user_id is not None:
            raise ValueError("owner_user_id must be null when operation is 'clear'.")
        if self.operation in {"assign", "reassign"} and self.owner_user_id is None:
            raise ValueError("owner_user_id is required for assign/reassign.")
        return self


class IncidentOwnerPatchResponse(BaseModel):
    incident_id: uuid.UUID
    owner_user_id: Optional[uuid.UUID] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[uuid.UUID] = None
    team_queue: Optional[IncidentQueue] = None
    last_activity_at_utc: Optional[datetime] = None


CaseOpsQueueSort = Literal["urgency", "readiness", "newest"]
CaseOpsBlockerFilter = Literal["any", "critical", "important", "none"]


class CaseOpsQueueBlockerCounts(BaseModel):
    total: int = 0
    critical: int = 0
    important: int = 0
    optional: int = 0


class CaseOpsQueueItem(BaseModel):
    incident_id: uuid.UUID
    case_status: IncidentCaseStatus
    owner_user_id: Optional[uuid.UUID] = None
    readiness_state: str = "not_ready"
    created_at_utc: Optional[datetime] = None
    last_activity_at_utc: Optional[datetime] = None
    severity: Optional[IncidentSeverity] = None
    adc_vehicle_id: Optional[VehicleId] = None
    adc_driver_id: Optional[DriverId] = None
    completeness_percent: int = Field(default=0, ge=0, le=100)
    blockers: CaseOpsQueueBlockerCounts = Field(
        default_factory=CaseOpsQueueBlockerCounts
    )


class CaseOpsQueueResponse(BaseModel):
    items: list[CaseOpsQueueItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class CaseOpsSummaryMetricsResponse(BaseModel):
    open_incidents: int = 0
    unassigned_incidents: int = 0
    blocked_incidents: int = 0
    export_aging_incidents: int = 0
    stalled_incidents: int = 0
    overdue_tasks: int = 0


class CaseOpsAlertsResponse(BaseModel):
    stalled: int = 0
    unassigned: int = 0
    overdue: int = 0
    blocked: int = 0
    export_aging: int = 0


class CaseTaskWidgetItem(BaseModel):
    task_id: uuid.UUID
    incident_id: uuid.UUID
    title: str
    status: str
    priority: str
    due_at_utc: Optional[datetime] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    created_at_utc: Optional[datetime] = None


class CaseTaskWidgetResponse(BaseModel):
    items: list[CaseTaskWidgetItem] = Field(default_factory=list)


class CaseOpsWorkspaceOwner(BaseModel):
    user_id: uuid.UUID
    email: Optional[EmailStrLike] = None


class CaseOpsWorkspaceCompletenessSection(BaseModel):
    name: str
    earned: int = 0
    possible: int = 0
    percent: int = Field(default=0, ge=0, le=100)
    status: str = "incomplete"
    missing_items: list[str] = Field(default_factory=list)


class CaseOpsWorkspaceCompleteness(BaseModel):
    percent: int = Field(default=0, ge=0, le=100)
    status: str = "incomplete"
    missing_items: list[str] = Field(default_factory=list)
    sections: list[CaseOpsWorkspaceCompletenessSection] = Field(default_factory=list)


class CaseOpsWorkspaceEvidenceSummary(BaseModel):
    total: int = 0
    captured: int = 0
    pending: int = 0
    unavailable: int = 0


class CaseOpsWorkspaceTaskItem(BaseModel):
    task_id: uuid.UUID
    title: str
    status: str
    priority: str
    due_at_utc: Optional[datetime] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    created_at_utc: Optional[datetime] = None


class CaseOpsWorkspaceNoteItem(BaseModel):
    note_id: uuid.UUID
    body: str
    note_type: Literal["standard", "tagged", "decision"] = "standard"
    tags: list[str] = Field(default_factory=list)
    created_by_user_id: Optional[uuid.UUID] = None
    created_at_utc: datetime
    edited_at_utc: Optional[datetime] = None


class CaseOpsWorkspaceActivityItem(BaseModel):
    source: Literal["event", "audit"]
    type: str
    occurred_at_utc: datetime
    actor_type: str
    actor_id: str
    detail: dict[str, Any] = Field(default_factory=dict)


class CaseOpsWorkspaceResponse(BaseModel):
    incident_id: uuid.UUID
    owner: Optional[CaseOpsWorkspaceOwner] = None
    case_status: IncidentCaseStatus
    readiness_state: str = "not_ready"
    completeness: CaseOpsWorkspaceCompleteness
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: CaseOpsWorkspaceEvidenceSummary = Field(
        default_factory=CaseOpsWorkspaceEvidenceSummary
    )
    missing_items: list[str] = Field(default_factory=list)
    open_tasks: list[CaseOpsWorkspaceTaskItem] = Field(default_factory=list)
    recent_notes: list[CaseOpsWorkspaceNoteItem] = Field(default_factory=list)
    activity: list[CaseOpsWorkspaceActivityItem] = Field(default_factory=list)




TaskStatus = Literal["open", "completed", "cancelled"]
TaskType = Literal["review", "evidence", "follow_up", "export", "other"]
TaskPriority = Literal["low", "medium", "high", "urgent"]


class IncidentTaskCreateRequest(BaseModel):
    title: ShortText
    description: Optional[LongText] = None
    task_type: TaskType = "other"
    priority: TaskPriority = "medium"
    due_at_utc: Optional[datetime] = None
    assigned_to_user_id: Optional[uuid.UUID] = None


class IncidentTaskPatchRequest(BaseModel):
    title: Optional[ShortText] = None
    description: Optional[LongText] = None
    task_type: Optional[TaskType] = None
    priority: Optional[TaskPriority] = None
    due_at_utc: Optional[datetime] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    status: Optional[TaskStatus] = None


class IncidentTaskCancelRequest(BaseModel):
    reason: Optional[ShortText] = None


class IncidentTaskItem(BaseModel):
    task_id: uuid.UUID
    incident_id: uuid.UUID
    title: str
    description: Optional[str] = None
    task_type: TaskType
    status: TaskStatus
    priority: TaskPriority
    due_at_utc: Optional[datetime] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_at_utc: Optional[datetime] = None
    assigned_by_user_id: Optional[uuid.UUID] = None
    created_by_user_id: Optional[uuid.UUID] = None
    created_at_utc: Optional[datetime] = None
    completed_at_utc: Optional[datetime] = None
    canceled_at_utc: Optional[datetime] = None
    canceled_reason: Optional[str] = None
    overdue: bool = False


class IncidentTaskListResponse(BaseModel):
    items: list[IncidentTaskItem] = Field(default_factory=list)

class IncidentNoteCreateRequest(BaseModel):
    body: LongText
    note_type: Literal["standard", "tagged", "decision"] = "standard"
    tags: list[ShortText] = Field(default_factory=list)


class IncidentNotePatchRequest(BaseModel):
    note_id: uuid.UUID
    body: LongText | None = None
    note_type: Literal["standard", "tagged", "decision"] | None = None
    tags: list[ShortText] | None = None


class IncidentNoteDeleteRequest(BaseModel):
    note_id: uuid.UUID


class IncidentNoteItem(BaseModel):
    note_id: uuid.UUID
    incident_id: uuid.UUID
    body: str
    note_type: Literal["standard", "tagged", "decision"] = "standard"
    tags: list[str] = Field(default_factory=list)
    created_by_user_id: Optional[uuid.UUID] = None
    created_at_utc: datetime
    edited: bool = False
    edited_by_user_id: Optional[uuid.UUID] = None
    edited_at_utc: Optional[datetime] = None
    updated_at_utc: datetime
    is_deleted: bool = False
    deleted_by_user_id: Optional[uuid.UUID] = None
    deleted_at_utc: Optional[datetime] = None


class IncidentNotesResponse(BaseModel):
    items: list[IncidentNoteItem] = Field(default_factory=list)


class MessagingReliabilityResponse(BaseModel):
    total: int = Field(default=0, ge=0)
    delivered: int = Field(default=0, ge=0)
    undelivered: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    success_rate_pct: int = Field(default=0, ge=0, le=100)


# ── Exports ─────────────────────────────────────────────────────────


class CreateExportResponse(BaseModel):
    export_id: uuid.UUID
    status: ExportStatus
    progress_stage: ExportProgressStage = "request_accepted"


class CreateExportRequest(BaseModel):
    incident_id: uuid.UUID
    export_type: ExportType = "court_defense"
    options_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_options_for_export_type(self):
        options = dict(self.options_json or {})
        requested_profile_id = str(
            options.get("profile_id")
            or options.get("profile")
            or DEFAULT_PROFILE_BY_EXPORT_TYPE[self.export_type]
        )
        profile = get_packet_profile(requested_profile_id)
        if profile.export_type != self.export_type:
            raise ValueError(
                f"options_json.profile_id '{requested_profile_id}' is not valid for export_type '{self.export_type}'"
            )

        allowed_keys = {
            "profile_id",
            "profile",
            "include_media",
            "include_raw_telemetry",
            "include_driver_statement",
            "inventory_mode",
        }
        unknown_keys = set(options.keys()) - allowed_keys
        if unknown_keys:
            raise ValueError(
                "options_json contains unsupported fields for packet profile exports"
            )

        defaults = profile.default_options()
        self.options_json = {
            **defaults,
            "include_media": bool(
                options.get("include_media", defaults["include_media"])
            ),
            "include_raw_telemetry": bool(
                options.get("include_raw_telemetry", defaults["include_raw_telemetry"])
            ),
            "include_driver_statement": bool(
                options.get(
                    "include_driver_statement", defaults["include_driver_statement"]
                )
            ),
            "inventory_mode": str(
                options.get("inventory_mode", defaults["inventory_mode"])
            ),
            "profile_id": requested_profile_id,
        }
        return self


class CreateExportEnqueueResponse(BaseModel):
    export_id: uuid.UUID
    incident_id: uuid.UUID
    export_type: ExportType
    status: ExportStatus
    created_at_utc: datetime


class RetryExportRequest(BaseModel):
    export_type: Optional[ExportType] = None
    options_json: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_retry_options(self):
        if self.export_type is None and self.options_json is None:
            return self
        target_export_type = self.export_type
        if target_export_type is None and self.options_json:
            requested_profile_id = self.options_json.get(
                "profile_id"
            ) or self.options_json.get("profile")
            if requested_profile_id:
                target_export_type = get_packet_profile(
                    str(requested_profile_id)
                ).export_type
        if target_export_type is None:
            return self

        options = dict(self.options_json or {})
        defaults = get_default_packet_profile(target_export_type).default_options()
        requested_profile_id = str(
            options.get("profile_id")
            or options.get("profile")
            or defaults["profile_id"]
        )
        profile = get_packet_profile(requested_profile_id)
        if profile.export_type != target_export_type:
            raise ValueError(
                f"options_json.profile_id '{requested_profile_id}' is not valid for export_type '{target_export_type}'"
            )
        self.options_json = {
            **defaults,
            "profile_id": requested_profile_id,
            "include_media": bool(
                options.get("include_media", defaults["include_media"])
            ),
            "include_raw_telemetry": bool(
                options.get("include_raw_telemetry", defaults["include_raw_telemetry"])
            ),
            "include_driver_statement": bool(
                options.get(
                    "include_driver_statement", defaults["include_driver_statement"]
                )
            ),
            "inventory_mode": str(
                options.get("inventory_mode", defaults["inventory_mode"])
            ),
        }
        return self


class DownloadExportResponse(BaseModel):
    export_id: uuid.UUID
    url: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    status: ExportStatus
    progress_stage: ExportProgressStage = "ready_for_download"


ExportContentKind = str
ExportContentClassification = Literal[
    "included",
    "unavailable",
    "excluded_by_option",
    "failed_to_retrieve",
]


class ExportStatusResponse(BaseModel):
    status: ExportStatus
    progress_stage: ExportProgressStage
    error_message: Optional[str] = None


class ExportContentsItem(BaseModel):
    kind: ExportContentKind
    item: Optional[str] = None
    path: Optional[str] = None
    classification: ExportContentClassification = "included"
    included: bool
    reason: Optional[str] = None
    byte_size: Optional[int] = None


class ExportContentsResponse(BaseModel):
    export_id: uuid.UUID
    status: ExportStatus
    progress_stage: ExportProgressStage
    file_manifest: list[ExportContentsItem] = Field(default_factory=list)
    missing_items: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)


class ExportDownloadAuditResponse(BaseModel):
    export_id: uuid.UUID
    downloads: list[EventSummary] = Field(default_factory=list)


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
    device_descriptor: Optional[ShortText] = None


class DriverOtpVerifyResponse(BaseModel):
    access_token: Annotated[str, StringConstraints(min_length=16)]
    refresh_token: Annotated[str, StringConstraints(min_length=16)]
    token_type: Literal["bearer"] = "bearer"


class DriverTokenRefreshRequest(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=16)]
    device_descriptor: Optional[ShortText] = None


class DriverSessionRevokeRequest(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=16)]


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
    sha256: Optional[
        Annotated[str, StringConstraints(min_length=16, max_length=128)]
    ] = None


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


class JobExecutionMetaSummary(BaseModel):
    failed: int = 0
    retrying: int = 0
    stuck: int = 0


class JobExecutionMetaItem(BaseModel):
    celery_task_id: str
    task_name: str
    task_type: str
    status: Literal["queued", "running", "retrying", "failed", "succeeded", "stuck"]
    retry_count: int = 0
    max_retries: int | None = None
    retry_category: str | None = None
    should_retry: bool | None = None
    next_retry_at_utc: datetime | None = None
    started_at_utc: datetime | None = None
    finished_at_utc: datetime | None = None
    last_heartbeat_at_utc: datetime | None = None
    last_error: str | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


class OpsIncidentItem(BaseModel):
    incident_id: uuid.UUID
    status: str
    created_at_utc: datetime | None = None
    adc_vehicle_id: str | None = None
    adc_driver_id: str | None = None
    reason: str


class OpsFailedNotificationItem(BaseModel):
    celery_task_id: str
    status: str
    retry_count: int = 0
    max_retries: int | None = None
    last_error: str | None = None
    updated_at_utc: datetime | None = None


class OpsFailedExportItem(BaseModel):
    export_id: uuid.UUID
    incident_id: uuid.UUID
    export_type: ExportType
    status: ExportStatus
    error_message: str | None = None
    updated_at_utc: datetime | None = None


class IntegrationHealthItem(BaseModel):
    integration_key: str
    status: Literal["healthy", "degraded"]
    failure_count: int = 0
    last_failure_at_utc: datetime | None = None
    details: str | None = None


IntegrationConnectionStatus = Literal["pending", "active", "inactive", "error"]
IntegrationOperationStatus = Literal[
    "requested",
    "submitted_to_provider",
    "processing_at_provider",
    "available",
    "downloaded",
    "unavailable",
    "queued",
    "running",
    "succeeded",
    "failed",
    "canceled",
]
EvidenceRequestStatus = Literal[
    "open", "in_progress", "fulfilled", "failed", "canceled"
]


class IntegrationConnectionHealthResponse(BaseModel):
    integration_id: uuid.UUID
    provider: str
    domain: str | None = None
    status: IntegrationConnectionStatus
    healthy: bool
    reason: str | None = None
    last_synced_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


class IntegrationConnectionUpdateRequest(BaseModel):
    status: IntegrationConnectionStatus | None = None
    credentials_ref: str | None = None
    config_json: dict[str, Any] | None = None


class IntegrationConnectionValidateResponse(BaseModel):
    integration_id: uuid.UUID
    valid: bool
    status: IntegrationConnectionStatus
    message: str


class IntegrationOperationDiagnosticsResponse(BaseModel):
    operation_id: uuid.UUID
    org_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    connection_id: uuid.UUID | None = None
    provider: str
    domain: str | None = None
    operation_type: str
    status: IntegrationOperationStatus
    correlation_id: str | None = None
    external_reference: str | None = None
    external_reference_id: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    error_code: str | None = None
    error_category: str | None = None
    error_provider_key: str | None = None
    error_retryable: bool | None = None
    error_user_facing_message: str | None = None
    error_operator_message: str | None = None
    requested_at_utc: datetime | None = None
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


class EvidenceRequestSummary(BaseModel):
    evidence_request_id: uuid.UUID
    operation_id: uuid.UUID | None = None
    provider: str
    domain: str | None = None
    status: EvidenceRequestStatus
    external_reference: str | None = None
    error_code: str | None = None
    error_category: str | None = None
    error_retryable: bool | None = None
    error_user_facing_message: str | None = None
    requested_at_utc: datetime | None = None
    fulfilled_at_utc: datetime | None = None


class EvidenceSummaryResponse(BaseModel):
    incident_id: uuid.UUID
    total_requests: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    provider_counts: dict[str, int] = Field(default_factory=dict)
    retryable_failures: int = 0
    requests: list[EvidenceRequestSummary] = Field(default_factory=list)


class EvidenceRetryActionRequest(BaseModel):
    evidence_request_ids: list[uuid.UUID] | None = None
    retry_failed_only: bool = True


class EvidenceRetryActionResponse(BaseModel):
    incident_id: uuid.UUID
    retried_count: int
    queued_operation_ids: list[uuid.UUID] = Field(default_factory=list)


class OpsAnomalyItem(BaseModel):
    audit_event_id: uuid.UUID
    occurred_at_utc: datetime
    action: str
    event_type: str
    outcome: str | None = None
    actor_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpsDashboardResponse(BaseModel):
    stuck_incidents: list[OpsIncidentItem] = Field(default_factory=list)
    missing_evidence_incidents: list[OpsIncidentItem] = Field(default_factory=list)
    failed_notifications: list[OpsFailedNotificationItem] = Field(default_factory=list)
    failed_exports: list[OpsFailedExportItem] = Field(default_factory=list)
    integration_health: list[IntegrationHealthItem] = Field(default_factory=list)
    recent_anomalies: list[OpsAnomalyItem] = Field(default_factory=list)
    org_messaging_reliability: MessagingReliabilityResponse = Field(
        default_factory=MessagingReliabilityResponse
    )
    case_metrics: dict[str, Any] = Field(default_factory=dict)


class AuditSearchResponseItem(BaseModel):
    audit_event_id: uuid.UUID
    org_id: uuid.UUID
    incident_id: uuid.UUID | None = None
    export_id: uuid.UUID | None = None
    actor_type: str
    actor_id: str
    action: str
    event_type: str
    outcome: str | None = None
    occurred_at_utc: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
