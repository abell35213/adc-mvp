"""Queue telematics evidence capture operations."""

from __future__ import annotations

import uuid
from typing import cast
from datetime import timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EvidenceRequest, ExternalMapping, Incident
from app.db.repo.evidence_requests import create_evidence_request
from app.db.repo.integration_operations import create_integration_operation
from app.services.integration_health_service import (
    set_evidence_request_status,
    transition_operation_status,
)
from app.tasks.evidence_tasks import capture_telematics_bundle


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dataset_windows(*, incident: Incident, window_start: str | None, window_end: str | None) -> dict[str, dict[str, str]]:
    if window_start and window_end:
        return {
            name: {"start": window_start, "end": window_end}
            for name in ("gps", "eld", "safety_events", "vehicle_state")
        }
    anchor = incident.created_at_utc
    gps_m = int(getattr(settings, "TELEMATICS_GPS_WINDOW_MINUTES", 30))
    eld_m = int(getattr(settings, "TELEMATICS_ELD_WINDOW_MINUTES", 60))
    state_m = int(getattr(settings, "TELEMATICS_VEHICLE_STATE_WINDOW_MINUTES", 60))
    return {
        "gps": {"start": _iso(anchor - timedelta(minutes=gps_m)), "end": _iso(anchor + timedelta(minutes=gps_m))},
        "eld": {"start": _iso(anchor - timedelta(minutes=eld_m)), "end": _iso(anchor + timedelta(minutes=eld_m))},
        "safety_events": {"start": _iso(anchor - timedelta(minutes=eld_m)), "end": _iso(anchor + timedelta(minutes=eld_m))},
        "vehicle_state": {
            "start": _iso(anchor - timedelta(minutes=state_m)),
            "end": _iso(anchor + timedelta(minutes=state_m)),
        },
    }


def _resolve_external_mappings(db: Session, *, incident: Incident) -> dict[str, str | None]:
    resolved_vehicle = incident.samsara_vehicle_id or incident.adc_vehicle_id
    resolved_driver = None
    mapping_query = db.query(ExternalMapping).filter(
        ExternalMapping.org_id == incident.org_id,
        ExternalMapping.provider == "samsara",
        ExternalMapping.status == "active",
    )
    if incident.adc_vehicle_id:
        vehicle_mapping = (
            mapping_query.filter(
                ExternalMapping.internal_entity_type == "vehicle",
                ExternalMapping.internal_entity_id == incident.adc_vehicle_id,
            )
            .order_by(ExternalMapping.updated_at_utc.desc())
            .first()
        )
        if vehicle_mapping is not None:
            resolved_vehicle = vehicle_mapping.external_reference
    if incident.adc_driver_id:
        driver_mapping = (
            mapping_query.filter(
                ExternalMapping.internal_entity_type == "driver",
                ExternalMapping.internal_entity_id == incident.adc_driver_id,
            )
            .order_by(ExternalMapping.updated_at_utc.desc())
            .first()
        )
        if driver_mapping is not None:
            resolved_driver = driver_mapping.external_reference
    return {"vehicle_id": cast(str | None, resolved_vehicle), "driver_id": cast(str | None, resolved_driver)}


def queue_telematics_capture(
    db: Session,
    *,
    org_id: uuid.UUID,
    incident_id: uuid.UUID,
    window_start: str | None,
    window_end: str | None,
    api_correlation_id: str,
    evidence_request_ids: list[uuid.UUID],
) -> uuid.UUID:
    """Create and queue telematics capture operation."""
    incident = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if incident is None:
        raise ValueError(f"Incident not found for telematics capture: {incident_id}")
    dataset_windows = _dataset_windows(
        incident=incident,
        window_start=window_start,
        window_end=window_end,
    )
    resolved_mappings = _resolve_external_mappings(db, incident=incident)

    operation_correlation_id = f"{api_correlation_id}:telematics"
    operation = create_integration_operation(
        db,
        org_id=org_id,
        incident_id=incident_id,
        provider="samsara",
        domain="telematics",
        operation_type="capture_telematics_bundle",
        status="queued",
        correlation_id=operation_correlation_id,
        payload_json={
            "window_start": window_start,
            "window_end": window_end,
            "dataset_windows": dataset_windows,
            "external_mappings": resolved_mappings,
            "evidence_request_ids": [str(er_id) for er_id in evidence_request_ids],
        },
    )
    transition_operation_status(
        db,
        operation=operation,
        to_status="queued",
        message="Telematics capture operation queued",
    )
    evidence_requests = (
        db.query(EvidenceRequest)
        .filter(EvidenceRequest.evidence_request_id.in_(evidence_request_ids))
        .all()
    )
    existing_refs = {request.external_reference for request in evidence_requests}
    for dataset_name in ("eld", "gps", "safety_events", "vehicle_state"):
        if dataset_name in existing_refs:
            continue
        evidence_requests.append(
            create_evidence_request(
                db,
                org_id=org_id,
                incident_id=incident_id,
                operation_id=operation.operation_id,
                provider="samsara",
                domain="telematics",
                status="open",
                correlation_id=operation_correlation_id,
                external_reference=dataset_name,
                request_payload_json={
                    "dataset": dataset_name,
                    "window": dataset_windows[dataset_name],
                    "external_mappings": resolved_mappings,
                },
            )
        )
    for evidence_request in evidence_requests:
        evidence_request.operation_id = operation.operation_id
        db.add(evidence_request)
    db.commit()

    for evidence_request in evidence_requests:
        set_evidence_request_status(db, evidence_request=evidence_request, status="in_progress")

    capture_telematics_bundle.delay(
        str(incident_id),
        window_start,
        window_end,
        operation_id=str(operation.operation_id),
        correlation_id=operation_correlation_id,
        dataset_windows=dataset_windows,
        external_mappings=resolved_mappings,
    )
    return operation.operation_id
