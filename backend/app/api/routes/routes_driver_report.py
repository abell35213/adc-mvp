"""Driver report patch/submit routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverIncidentReportNarrativePatchRequest,
    DriverIncidentReportPartiesPatchRequest,
    DriverIncidentReportPatchRequest,
    DriverIncidentReportScenePatchRequest,
    DriverIncidentReportWriteResponse,
)
from app.core.deps import get_current_driver
from app.db.models import Driver
from app.db.session import get_db
from app.services.driver_report_service import (
    patch_report_sections,
    submit_driver_report,
)

router = APIRouter()


@router.patch(
    "/incidents/{incident_id}/scene",
    response_model=DriverIncidentReportWriteResponse,
)
def patch_incident_scene(
    incident_id: uuid.UUID,
    body: DriverIncidentReportScenePatchRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    updated_sections = patch_report_sections(
        db,
        incident_id=incident_id,
        driver=driver,
        patch={"scene": body.scene},
    )
    return DriverIncidentReportWriteResponse(
        incident_id=incident_id,
        updated_sections=updated_sections,
    )


@router.patch(
    "/incidents/{incident_id}/parties",
    response_model=DriverIncidentReportWriteResponse,
)
def patch_incident_parties(
    incident_id: uuid.UUID,
    body: DriverIncidentReportPartiesPatchRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    updated_sections = patch_report_sections(
        db,
        incident_id=incident_id,
        driver=driver,
        patch={"parties": body.parties},
    )
    return DriverIncidentReportWriteResponse(
        incident_id=incident_id,
        updated_sections=updated_sections,
    )


@router.patch(
    "/incidents/{incident_id}/narrative",
    response_model=DriverIncidentReportWriteResponse,
)
def patch_incident_narrative(
    incident_id: uuid.UUID,
    body: DriverIncidentReportNarrativePatchRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    updated_sections = patch_report_sections(
        db,
        incident_id=incident_id,
        driver=driver,
        patch={"narrative": body.narrative},
    )
    return DriverIncidentReportWriteResponse(
        incident_id=incident_id,
        updated_sections=updated_sections,
    )


@router.patch(
    "/incidents/{incident_id}/report",
    response_model=DriverIncidentReportWriteResponse,
)
def patch_incident_report(
    incident_id: uuid.UUID,
    body: DriverIncidentReportPatchRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    patch: dict = {}
    if body.scene is not None:
        patch["scene"] = body.scene
    if body.parties is not None:
        patch["parties"] = body.parties
    if body.narrative is not None:
        patch["narrative"] = body.narrative

    updated_sections = patch_report_sections(
        db,
        incident_id=incident_id,
        driver=driver,
        patch=patch,
    )
    return DriverIncidentReportWriteResponse(
        incident_id=incident_id,
        updated_sections=updated_sections,
    )


@router.post(
    "/incidents/{incident_id}/submit-driver-report",
    response_model=DriverIncidentReportWriteResponse,
)
def submit_incident_driver_report(
    incident_id: uuid.UUID,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    submit_driver_report(
        db,
        incident_id=incident_id,
        driver=driver,
    )
    return DriverIncidentReportWriteResponse(
        incident_id=incident_id,
        updated_sections=[],
        submitted=True,
    )
