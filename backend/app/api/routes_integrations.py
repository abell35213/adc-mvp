"""Integration and evidence diagnostics API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.schemas import (
    EvidenceRequestSummary,
    EvidenceRetryActionRequest,
    EvidenceRetryActionResponse,
    EvidenceSummaryResponse,
    IntegrationConnectionHealthResponse,
    IntegrationConnectionUpdateRequest,
    IntegrationConnectionValidateResponse,
    IntegrationOperationDiagnosticsResponse,
)
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.logging import get_request_id
from app.db.models import (
    EvidenceRequest,
    IntegrationConnection,
    IntegrationOperation,
    User,
)
from app.db.session import get_db
from app.integrations.webhooks.handlers import (
    persist_twilio_voice_callback,
    process_twilio_status_callback,
)
from app.integrations.webhooks.signatures import (
    parse_form_encoded_body,
    validate_twilio_signature,
)
from app.security.authn import build_user_auth_context
from app.services.dashcam_capture_service import queue_dashcam_capture
from app.services.telematics_capture_service import queue_telematics_capture

router = APIRouter()


@router.get("/org/integrations", response_model=list[IntegrationConnectionHealthResponse])
def list_org_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(IntegrationConnection)
        .filter(IntegrationConnection.org_id.in_(context.org_ids))
        .order_by(IntegrationConnection.updated_at_utc.desc())
        .all()
    )
    return [
        IntegrationConnectionHealthResponse(
            integration_id=row.connection_id,
            provider=row.provider,
            domain=row.domain,
            status=row.status,
            healthy=row.status in {"active", "pending"},
            reason=None if row.status in {"active", "pending"} else "Connection not healthy",
            last_synced_at_utc=row.last_synced_at_utc,
            updated_at_utc=row.updated_at_utc,
        )
        for row in rows
    ]


@router.get("/org/integrations/{integration_id}", response_model=IntegrationConnectionHealthResponse)
def get_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=row.status in {"active", "pending"},
        reason=None if row.status in {"active", "pending"} else "Connection not healthy",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.post(
    "/org/integrations/{integration_id}/validate",
    response_model=IntegrationConnectionValidateResponse,
)
def validate_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    valid = bool(row.credentials_ref) and row.status != "inactive"
    return IntegrationConnectionValidateResponse(
        integration_id=row.connection_id,
        valid=valid,
        status=row.status,
        message="Connection validated" if valid else "Connection missing credentials or disabled",
    )


@router.patch("/org/integrations/{integration_id}", response_model=IntegrationConnectionHealthResponse)
def patch_org_integration(
    integration_id: uuid.UUID,
    payload: IntegrationConnectionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    updates = payload.model_dump(exclude_unset=True)
    for field in ("status", "credentials_ref", "config_json"):
        if field in updates:
            setattr(row, field, updates[field])
    db.add(row)
    db.commit()
    db.refresh(row)

    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=row.status in {"active", "pending"},
        reason=None if row.status in {"active", "pending"} else "Connection not healthy",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.post("/org/integrations/{integration_id}/disable", response_model=IntegrationConnectionHealthResponse)
def disable_org_integration(
    integration_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.connection_id == integration_id,
            IntegrationConnection.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    row.status = "inactive"
    db.add(row)
    db.commit()
    db.refresh(row)

    return IntegrationConnectionHealthResponse(
        integration_id=row.connection_id,
        provider=row.provider,
        domain=row.domain,
        status=row.status,
        healthy=False,
        reason="Connection disabled",
        last_synced_at_utc=row.last_synced_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


@router.get("/integration-operations", response_model=list[IntegrationOperationDiagnosticsResponse])
def list_integration_operations(
    incident_id: uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    query = db.query(IntegrationOperation).filter(IntegrationOperation.org_id.in_(context.org_ids))
    if incident_id is not None:
        query = query.filter(IntegrationOperation.incident_id == incident_id)
    if status is not None:
        query = query.filter(IntegrationOperation.status == status)
    if provider is not None:
        query = query.filter(IntegrationOperation.provider == provider)
    rows = query.order_by(IntegrationOperation.requested_at_utc.desc()).all()
    return [IntegrationOperationDiagnosticsResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get(
    "/integration-operations/{operation_id}",
    response_model=IntegrationOperationDiagnosticsResponse,
)
def get_integration_operation(
    operation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    row = (
        db.query(IntegrationOperation)
        .filter(
            IntegrationOperation.operation_id == operation_id,
            IntegrationOperation.org_id.in_(context.org_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration operation not found")
    return IntegrationOperationDiagnosticsResponse.model_validate(row, from_attributes=True)


@router.get(
    "/incidents/{incident_id}/evidence-requests",
    response_model=list[EvidenceRequestSummary],
)
def list_incident_evidence_requests(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(EvidenceRequest)
        .filter(
            EvidenceRequest.incident_id == incident_id,
            EvidenceRequest.org_id.in_(context.org_ids),
        )
        .order_by(EvidenceRequest.requested_at_utc.desc())
        .all()
    )
    return [EvidenceRequestSummary.model_validate(row, from_attributes=True) for row in rows]


@router.post(
    "/incidents/{incident_id}/evidence-requests/retry",
    response_model=EvidenceRetryActionResponse,
)
def retry_incident_evidence_requests(
    incident_id: uuid.UUID,
    payload: EvidenceRetryActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    query = db.query(EvidenceRequest).filter(
        EvidenceRequest.incident_id == incident_id,
        EvidenceRequest.org_id.in_(context.org_ids),
    )
    if payload.evidence_request_ids:
        query = query.filter(EvidenceRequest.evidence_request_id.in_(payload.evidence_request_ids))
    if payload.retry_failed_only:
        query = query.filter(EvidenceRequest.status == "failed")

    rows = query.order_by(EvidenceRequest.requested_at_utc.desc()).all()
    if not rows:
        return EvidenceRetryActionResponse(incident_id=incident_id, retried_count=0, queued_operation_ids=[])

    correlation_id = get_request_id() or str(uuid.uuid4())
    operation_ids: list[uuid.UUID] = []

    dashcam_ids = [row.evidence_request_id for row in rows if row.domain == "dashcam"]
    telematics_ids = [row.evidence_request_id for row in rows if row.domain == "telematics"]
    org_id = rows[0].org_id
    if org_id is None:
        raise HTTPException(status_code=422, detail="Evidence requests are missing org_id")

    if dashcam_ids:
        operation_ids.append(
            queue_dashcam_capture(
                db,
                org_id=org_id,
                incident_id=incident_id,
                window_start=None,
                window_end=None,
                api_correlation_id=correlation_id,
                evidence_request_ids=dashcam_ids,
            )
        )
    if telematics_ids:
        operation_ids.append(
            queue_telematics_capture(
                db,
                org_id=org_id,
                incident_id=incident_id,
                window_start=None,
                window_end=None,
                api_correlation_id=correlation_id,
                evidence_request_ids=telematics_ids,
            )
        )

    return EvidenceRetryActionResponse(
        incident_id=incident_id,
        retried_count=len(rows),
        queued_operation_ids=operation_ids,
    )


@router.get("/incidents/{incident_id}/evidence-summary", response_model=EvidenceSummaryResponse)
def get_incident_evidence_summary(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    rows = (
        db.query(EvidenceRequest)
        .filter(
            EvidenceRequest.incident_id == incident_id,
            EvidenceRequest.org_id.in_(context.org_ids),
        )
        .order_by(EvidenceRequest.requested_at_utc.desc())
        .all()
    )

    status_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    retryable_failures = 0
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
        provider_counts[row.provider] = provider_counts.get(row.provider, 0) + 1
        if row.status == "failed" and row.error_retryable:
            retryable_failures += 1

    return EvidenceSummaryResponse(
        incident_id=incident_id,
        total_requests=len(rows),
        status_counts=status_counts,
        provider_counts=provider_counts,
        retryable_failures=retryable_failures,
        requests=[EvidenceRequestSummary.model_validate(row, from_attributes=True) for row in rows],
    )


@router.post("/provider-webhooks/twilio/voice")
async def provider_twilio_voice_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    params = parse_form_encoded_body(raw_body)
    signature_valid, signature_error = validate_twilio_signature(
        auth_token=settings.TWILIO_AUTH_TOKEN,
        request_url=str(request.url),
        params=params,
        provided_signature=request.headers.get("X-Twilio-Signature"),
    )
    result = persist_twilio_voice_callback(
        db,
        payload=params,
        raw_payload=raw_body.decode("utf-8", errors="ignore"),
        signature_valid=signature_valid,
        signature_error=signature_error,
    )
    return Response(status_code=result.status_code, content=result.body.get("detail", "ok"))


@router.post("/provider-webhooks/twilio/status")
async def provider_twilio_status_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    params = parse_form_encoded_body(raw_body)
    signature_valid, signature_error = validate_twilio_signature(
        auth_token=settings.TWILIO_AUTH_TOKEN,
        request_url=str(request.url),
        params=params,
        provided_signature=request.headers.get("X-Twilio-Signature"),
    )
    result = process_twilio_status_callback(
        db,
        payload=params,
        raw_payload=raw_body.decode("utf-8", errors="ignore"),
        signature_valid=signature_valid,
        signature_error=signature_error,
    )
    return result.body
