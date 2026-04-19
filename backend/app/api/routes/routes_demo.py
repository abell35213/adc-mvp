"""Demo orchestration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.commercial.demo import (
    DEFAULT_SCENARIO_KEY,
    ensure_demo_org,
    launch_scenario,
    list_scenarios,
    reset_demo_tenant,
    seed_demo_tenant,
)
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.security.authn import build_user_auth_context
from app.security.permissions import can_mutate_demo_tenant

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoScenarioSummary(BaseModel):
    scenario_id: str
    name: str
    description: str
    is_active: bool
    seed_batch_id: str | None = None


class DemoResetResponse(BaseModel):
    deleted: dict[str, int]


class DemoSeedRequest(BaseModel):
    scenario_id: str = DEFAULT_SCENARIO_KEY


class DemoSeedResponse(BaseModel):
    scenario_id: str
    seed_batch_id: str
    incident_id: str
    export_id: str


class DemoLaunchResponse(DemoSeedResponse):
    pass


def _require_demo_mutation_role(user: User) -> None:
    if not can_mutate_demo_tenant(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )


@router.get("/scenarios", response_model=list[DemoScenarioSummary])
def get_demo_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = build_user_auth_context(db, current_user)
    ensure_demo_org(db, org_id=context.org_ids[0])
    return list_scenarios(db, org_id=context.org_ids[0])


@router.post("/reset", response_model=DemoResetResponse)
def post_demo_reset(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_demo_mutation_role(current_user)
    context = build_user_auth_context(db, current_user)
    deleted = reset_demo_tenant(db, org_id=context.org_ids[0], actor_id=str(current_user.id))
    return DemoResetResponse(deleted=deleted)


@router.post("/seed", response_model=DemoSeedResponse)
def post_demo_seed(
    payload: DemoSeedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_demo_mutation_role(current_user)
    context = build_user_auth_context(db, current_user)
    try:
        seeded = seed_demo_tenant(
            db,
            org_id=context.org_ids[0],
            actor=current_user,
            scenario_key=payload.scenario_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown scenario") from exc
    return DemoSeedResponse(**seeded)


@router.post("/scenarios/{scenario_id}/launch", response_model=DemoLaunchResponse)
def post_demo_launch(
    scenario_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_demo_mutation_role(current_user)
    context = build_user_auth_context(db, current_user)
    try:
        seeded = launch_scenario(
            db,
            org_id=context.org_ids[0],
            actor=current_user,
            scenario_id=scenario_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown scenario") from exc
    return DemoLaunchResponse(**seeded)
