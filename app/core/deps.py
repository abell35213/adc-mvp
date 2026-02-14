"""FastAPI dependencies for authentication and role-based access control.

This module provides helpers to extract and validate the currently
authenticated user or driver from a JWT and to enforce role-based access
restrictions. It is largely based on the upstream implementation but
introduces ``require_roles`` for enforcing that a user has at least one
role from a provided list. Roles are stored as a comma-separated string on
the ``User`` model. If no matching role is found, a ``403 Forbidden``
error is raised.
"""

from __future__ import annotations

import uuid
from typing import Iterable, Callable, TypeVar

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.db.repo.users import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Decode a Bearer token (header or httpOnly cookie) and return the active User row.

    If the token is missing or invalid, raises ``401 Unauthorized``. This
    function replicates the logic from the upstream project.
    """
    token: str | None = None
    # Prefer Authorization header
    if creds is not None:
        token = creds.credentials
    else:
        # Fall back to httpOnly cookie
        token = request.cookies.get("access_token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    user = get_user_by_id(db, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def get_current_driver(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Decode a driver-scoped JWT and return the active Driver row.

    Drivers are authenticated via a token with ``scope=driver``. The token
    subject is expected to be the driver's UUID. If authentication fails,
    appropriate ``401`` or ``403`` errors are raised.
    """
    from app.db.repo.drivers import get_driver_by_id

    token: str | None = None
    if creds is not None:
        token = creds.credentials
    else:
        token = request.cookies.get("access_token")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("scope") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a driver token",
        )

    driver_id = payload.get("sub")
    if driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    try:
        driver_uuid = uuid.UUID(driver_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject in token",
        )
    driver = get_driver_by_id(db, driver_uuid)
    if driver is None or not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not found or inactive",
        )
    return driver


T = TypeVar("T")


def require_roles(roles: Iterable[str]) -> Callable[[T], T]:
    """Create a FastAPI dependency that requires the current user to have at least one of the given roles.

    Example usage::

        @router.get("/admin-only")
        def admin_endpoint(current_user: User = Depends(require_roles(["admin"]))):
            ...

    Roles are matched case-insensitively and trimmed of whitespace. If the
    current user lacks all of the required roles, a 403 error is thrown.
    """

    required = {r.strip().lower() for r in roles if r}

    def dependency(current_user: T = Depends(get_current_user)) -> T:
        # Roles may be stored as comma-separated values or a single string
        user_roles = set(
            part.strip().lower()
            for part in (current_user.role or "").split(",")
            if part.strip()
        )
        if required and user_roles.isdisjoint(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency