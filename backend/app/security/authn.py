"""Authentication context helpers backed by persisted DB relationships."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Driver, User
from app.db.repo.users import get_user_org_ids


@dataclass(frozen=True)
class UserAuthContext:
    """Authenticated web user context."""

    user: User
    org_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class DriverAuthContext:
    """Authenticated driver context."""

    driver: Driver
    org_id: uuid.UUID


def build_user_auth_context(db: Session, user: User) -> UserAuthContext:
    """Resolve org memberships from DB for an authenticated user."""
    org_ids = tuple(get_user_org_ids(db, user.id))
    if not org_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    return UserAuthContext(user=user, org_ids=org_ids)


def build_driver_auth_context(driver: Driver) -> DriverAuthContext:
    """Resolve driver org context from persisted driver row."""
    if driver.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    return DriverAuthContext(driver=driver, org_id=driver.org_id)
