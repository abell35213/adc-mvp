"""Manual-entry REST endpoints for dispatch / weigh / loading dock evidence.

Per the Phase-3 plan (clarifying answer #1): TMS sync is the primary source
of truth, but every org must be able to enter the same evidence by hand
when no :class:`TmsConnection` is configured. Manual rows have
``external_id IS NULL`` and ``source='manual'``; TMS upserts (keyed on
``(org_id, external_id)``) never touch them, so the two paths coexist
safely.

All endpoints are org-scoped and gated by the existing
``INCIDENT_READ`` / ``INCIDENT_WRITE`` capabilities — the same RBAC
already used by case-ops manual entry of incident notes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import (
    require_note_operations_permission,
    require_workspace_view_permission,
)
from app.db.models import (
    DispatchInstruction,
    LoadingDockReport,
    User,
    WeighStationReport,
)
from app.db.repo import (
    dispatch_instructions as dispatch_repo,
    loading_dock_reports as dock_repo,
    weigh_station_reports as weigh_repo,
)
from app.db.session import get_db
from app.security.authn import build_user_auth_context

router = APIRouter()


# ── Pydantic request / response models ────────────────────────────────


class _BaseConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DispatchInstructionCreate(_BaseConfig):
    adc_driver_id: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    adc_trailer_id: Optional[str] = None
    incident_id: Optional[uuid.UUID] = None
    dispatch_id: Optional[str] = None
    load_number: Optional[str] = None
    dispatched_by: Optional[str] = None
    dispatched_at_utc: Optional[datetime] = None
    pickup_appointment_at_utc: Optional[datetime] = None
    delivery_appointment_at_utc: Optional[datetime] = None
    eta_at_utc: Optional[datetime] = None
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None
    hos_remaining_drive_minutes: Optional[int] = Field(default=None, ge=0)
    hos_remaining_duty_minutes: Optional[int] = Field(default=None, ge=0)
    forced_dispatch_flag: bool = False
    notes: Optional[str] = None


class DispatchInstructionPatch(_BaseConfig):
    adc_driver_id: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    adc_trailer_id: Optional[str] = None
    incident_id: Optional[uuid.UUID] = None
    dispatch_id: Optional[str] = None
    load_number: Optional[str] = None
    dispatched_by: Optional[str] = None
    dispatched_at_utc: Optional[datetime] = None
    pickup_appointment_at_utc: Optional[datetime] = None
    delivery_appointment_at_utc: Optional[datetime] = None
    eta_at_utc: Optional[datetime] = None
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None
    hos_remaining_drive_minutes: Optional[int] = Field(default=None, ge=0)
    hos_remaining_duty_minutes: Optional[int] = Field(default=None, ge=0)
    forced_dispatch_flag: Optional[bool] = None
    notes: Optional[str] = None


class DispatchInstructionItem(_BaseConfig):
    id: uuid.UUID
    org_id: uuid.UUID
    adc_driver_id: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    adc_trailer_id: Optional[str] = None
    incident_id: Optional[uuid.UUID] = None
    dispatch_id: Optional[str] = None
    load_number: Optional[str] = None
    dispatched_by: Optional[str] = None
    dispatched_at_utc: Optional[datetime] = None
    pickup_appointment_at_utc: Optional[datetime] = None
    delivery_appointment_at_utc: Optional[datetime] = None
    eta_at_utc: Optional[datetime] = None
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None
    hos_remaining_drive_minutes: Optional[int] = None
    hos_remaining_duty_minutes: Optional[int] = None
    forced_dispatch_flag: bool = False
    notes: Optional[str] = None
    source: str
    external_id: Optional[str] = None
    created_at_utc: datetime
    updated_at_utc: datetime


class DispatchInstructionListResponse(_BaseConfig):
    items: list[DispatchInstructionItem] = Field(default_factory=list)


WeighResult = Literal["pass", "bypass", "cited", "out_of_service"]


class WeighStationReportCreate(_BaseConfig):
    adc_vehicle_id: Optional[str] = None
    adc_trailer_id: Optional[str] = None
    dispatch_instruction_id: Optional[uuid.UUID] = None
    incident_id: Optional[uuid.UUID] = None
    weighed_at_utc: Optional[datetime] = None
    station_name: Optional[str] = None
    station_location: Optional[str] = None
    ticket_number: Optional[str] = None
    gross_weight_lb: Optional[int] = Field(default=None, ge=0)
    steer_axle_weight_lb: Optional[int] = Field(default=None, ge=0)
    drive_axle_weight_lb: Optional[int] = Field(default=None, ge=0)
    trailer_axle_weight_lb: Optional[int] = Field(default=None, ge=0)
    legal_limit_lb: Optional[int] = Field(default=None, ge=0)
    is_over_legal_limit: Optional[bool] = None
    result: Optional[WeighResult] = None
    citation_text: Optional[str] = None
    inspector_name: Optional[str] = None
    doc_artifact_id: Optional[uuid.UUID] = None


class WeighStationReportPatch(WeighStationReportCreate):
    pass


class WeighStationReportItem(_BaseConfig):
    id: uuid.UUID
    org_id: uuid.UUID
    adc_vehicle_id: Optional[str] = None
    adc_trailer_id: Optional[str] = None
    dispatch_instruction_id: Optional[uuid.UUID] = None
    incident_id: Optional[uuid.UUID] = None
    weighed_at_utc: Optional[datetime] = None
    station_name: Optional[str] = None
    station_location: Optional[str] = None
    ticket_number: Optional[str] = None
    gross_weight_lb: Optional[int] = None
    steer_axle_weight_lb: Optional[int] = None
    drive_axle_weight_lb: Optional[int] = None
    trailer_axle_weight_lb: Optional[int] = None
    legal_limit_lb: Optional[int] = None
    is_over_legal_limit: bool = False
    result: Optional[WeighResult] = None
    citation_text: Optional[str] = None
    inspector_name: Optional[str] = None
    doc_artifact_id: Optional[uuid.UUID] = None
    source: str
    external_id: Optional[str] = None
    created_at_utc: datetime
    updated_at_utc: datetime


class WeighStationReportListResponse(_BaseConfig):
    items: list[WeighStationReportItem] = Field(default_factory=list)


class LoadingDockReportCreate(_BaseConfig):
    adc_trailer_id: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    dispatch_instruction_id: Optional[uuid.UUID] = None
    incident_id: Optional[uuid.UUID] = None
    loaded_at_utc: Optional[datetime] = None
    facility_name: Optional[str] = None
    facility_address: Optional[str] = None
    commodity: Optional[str] = None
    pieces: Optional[int] = Field(default=None, ge=0)
    gross_weight_lb: Optional[int] = Field(default=None, ge=0)
    net_weight_lb: Optional[int] = Field(default=None, ge=0)
    seal_number: Optional[str] = None
    securement_method: Optional[str] = None
    weight_distribution_notes: Optional[str] = None
    is_overloaded: bool = False
    is_improperly_loaded: bool = False
    loaded_by: Optional[str] = None
    dock_supervisor: Optional[str] = None
    signature_artifact_id: Optional[uuid.UUID] = None


class LoadingDockReportPatch(LoadingDockReportCreate):
    is_overloaded: Optional[bool] = None  # type: ignore[assignment]
    is_improperly_loaded: Optional[bool] = None  # type: ignore[assignment]


class LoadingDockReportItem(_BaseConfig):
    id: uuid.UUID
    org_id: uuid.UUID
    adc_trailer_id: Optional[str] = None
    adc_vehicle_id: Optional[str] = None
    dispatch_instruction_id: Optional[uuid.UUID] = None
    incident_id: Optional[uuid.UUID] = None
    loaded_at_utc: Optional[datetime] = None
    facility_name: Optional[str] = None
    facility_address: Optional[str] = None
    commodity: Optional[str] = None
    pieces: Optional[int] = None
    gross_weight_lb: Optional[int] = None
    net_weight_lb: Optional[int] = None
    seal_number: Optional[str] = None
    securement_method: Optional[str] = None
    weight_distribution_notes: Optional[str] = None
    is_overloaded: bool = False
    is_improperly_loaded: bool = False
    loaded_by: Optional[str] = None
    dock_supervisor: Optional[str] = None
    signature_artifact_id: Optional[uuid.UUID] = None
    source: str
    external_id: Optional[str] = None
    created_at_utc: datetime
    updated_at_utc: datetime


class LoadingDockReportListResponse(_BaseConfig):
    items: list[LoadingDockReportItem] = Field(default_factory=list)


class AttachArtifactRequest(_BaseConfig):
    artifact_id: uuid.UUID


# ── Helpers ──────────────────────────────────────────────────────────


def _require_org_membership(
    db: Session, *, current_user: User, org_id: uuid.UUID
) -> None:
    """Reject the request unless ``current_user`` belongs to ``org_id``."""
    context = build_user_auth_context(db, current_user)
    if org_id not in context.org_ids:
        raise HTTPException(status_code=404, detail="Org not found")


def _to_dispatch_item(record: DispatchInstruction) -> DispatchInstructionItem:
    return DispatchInstructionItem.model_validate(
        {c.name: getattr(record, c.name) for c in record.__table__.columns}
    )


def _to_weigh_item(record: WeighStationReport) -> WeighStationReportItem:
    return WeighStationReportItem.model_validate(
        {c.name: getattr(record, c.name) for c in record.__table__.columns}
    )


def _to_dock_item(record: LoadingDockReport) -> LoadingDockReportItem:
    return LoadingDockReportItem.model_validate(
        {c.name: getattr(record, c.name) for c in record.__table__.columns}
    )


def _writable_fields(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


# ── Dispatch Instructions ────────────────────────────────────────────


@router.get(
    "/orgs/{org_id}/dispatch-instructions",
    response_model=DispatchInstructionListResponse,
)
def list_dispatch_instructions(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    rows = dispatch_repo.list_for_org(db, org_id=org_id)
    return DispatchInstructionListResponse(
        items=[_to_dispatch_item(r) for r in rows]
    )


@router.post(
    "/orgs/{org_id}/dispatch-instructions",
    response_model=DispatchInstructionItem,
)
def create_dispatch_instruction(
    org_id: uuid.UUID,
    payload: DispatchInstructionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = dispatch_repo.create_manual(
        db, org_id=org_id, fields=_writable_fields(payload)
    )
    return _to_dispatch_item(record)


@router.patch(
    "/orgs/{org_id}/dispatch-instructions/{record_id}",
    response_model=DispatchInstructionItem,
)
def patch_dispatch_instruction(
    org_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: DispatchInstructionPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = dispatch_repo.get_by_id(db, org_id=org_id, dispatch_id=record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dispatch instruction not found")
    record = dispatch_repo.update_manual(
        db, instruction=record, fields=_writable_fields(payload)
    )
    return _to_dispatch_item(record)


# ── Weigh Station Reports ────────────────────────────────────────────


@router.get(
    "/orgs/{org_id}/weigh-station-reports",
    response_model=WeighStationReportListResponse,
)
def list_weigh_station_reports(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    rows = weigh_repo.list_for_org(db, org_id=org_id)
    return WeighStationReportListResponse(
        items=[_to_weigh_item(r) for r in rows]
    )


@router.post(
    "/orgs/{org_id}/weigh-station-reports",
    response_model=WeighStationReportItem,
)
def create_weigh_station_report(
    org_id: uuid.UUID,
    payload: WeighStationReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = weigh_repo.create_manual(
        db, org_id=org_id, fields=_writable_fields(payload)
    )
    return _to_weigh_item(record)


@router.patch(
    "/orgs/{org_id}/weigh-station-reports/{record_id}",
    response_model=WeighStationReportItem,
)
def patch_weigh_station_report(
    org_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: WeighStationReportPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = weigh_repo.get_by_id(db, org_id=org_id, report_id=record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Weigh station report not found")
    record = weigh_repo.update_manual(
        db, report=record, fields=_writable_fields(payload)
    )
    return _to_weigh_item(record)


# ── Loading Dock Reports ─────────────────────────────────────────────


@router.get(
    "/orgs/{org_id}/loading-dock-reports",
    response_model=LoadingDockReportListResponse,
)
def list_loading_dock_reports(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_workspace_view_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    rows = dock_repo.list_for_org(db, org_id=org_id)
    return LoadingDockReportListResponse(
        items=[_to_dock_item(r) for r in rows]
    )


@router.post(
    "/orgs/{org_id}/loading-dock-reports",
    response_model=LoadingDockReportItem,
)
def create_loading_dock_report(
    org_id: uuid.UUID,
    payload: LoadingDockReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = dock_repo.create_manual(
        db, org_id=org_id, fields=_writable_fields(payload)
    )
    return _to_dock_item(record)


@router.patch(
    "/orgs/{org_id}/loading-dock-reports/{record_id}",
    response_model=LoadingDockReportItem,
)
def patch_loading_dock_report(
    org_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: LoadingDockReportPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = dock_repo.get_by_id(db, org_id=org_id, report_id=record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Loading dock report not found")
    record = dock_repo.update_manual(
        db, report=record, fields=_writable_fields(payload)
    )
    return _to_dock_item(record)


@router.post(
    "/orgs/{org_id}/loading-dock-reports/{record_id}/photos",
    response_model=LoadingDockReportItem,
)
def attach_photo_to_loading_dock_report(
    org_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: AttachArtifactRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_note_operations_permission),
):
    """Link an existing artifact (e.g. an uploaded photo) to a dock report.

    The artifact upload pipeline is unchanged; this endpoint just sets the
    ``loading_dock_report_id`` FK so the artifact surfaces under the
    report's ``photos`` list in the crash brief.
    """
    _require_org_membership(db, current_user=current_user, org_id=org_id)
    record = dock_repo.get_by_id(db, org_id=org_id, report_id=record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Loading dock report not found")
    from app.db.models import Artifact

    artifact = (
        db.query(Artifact)
        .filter(Artifact.org_id == org_id, Artifact.artifact_id == payload.artifact_id)
        .first()
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    dock_repo.attach_artifact(
        db, artifact=artifact, loading_dock_report_id=record.id
    )
    return _to_dock_item(record)
