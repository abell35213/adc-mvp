"""FastAPI dependencies and authorization helpers."""

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import Driver, User
from app.db.repo.drivers import get_driver_by_id
from app.db.repo.users import get_user_by_id, get_user_org_ids
from app.db.session import get_db
from app.security.csrf import validate_csrf_request
from app.security.permissions import Capability, get_user_capabilities, normalize_role
from app.security.session import validate_session

_bearer = HTTPBearer(auto_error=False)


def _read_access_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> str:
    """Resolve JWT from Authorization header or access_token cookie."""
    if creds is not None:
        return creds.credentials

    token = request.cookies.get("access_token")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return token


def _decode_subject_uuid(payload: dict, *, detail: str = "Invalid subject in token") -> uuid.UUID:
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from exc


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Decode a user JWT and return the active User row."""
    validate_csrf_request(request)
    token = _read_access_token(request, creds)

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    sid = payload.get("sid")
    if sid:
        try:
            validate_session(db, session_id=uuid.UUID(sid), expected_client_type="web")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

    user_id = _decode_subject_uuid(payload)
    user = get_user_by_id(db, user_id)
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
) -> Driver:
    """Decode a driver-scoped JWT and return the active Driver row."""
    validate_csrf_request(request)
    token = _read_access_token(request, creds)

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

    sid = payload.get("sid")
    if sid:
        try:
            validate_session(db, session_id=uuid.UUID(sid), expected_client_type="driver_mobile")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

    driver_id = _decode_subject_uuid(payload)
    driver = get_driver_by_id(db, driver_id)
    if driver is None or not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not found or inactive",
        )
    return driver


def require_user_role(*allowed_roles: str) -> Callable[[User], User]:
    """Create a dependency that enforces a user's role."""
    allowed = {normalize_role(role) for role in allowed_roles}

    def _require_role(current_user: User = Depends(get_current_user)) -> User:
        if normalize_role(current_user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return _require_role


def require_capabilities(*required_capabilities: Capability | str) -> Callable[[User], User]:
    """Create a dependency that enforces a user's capabilities."""

    required = {
        capability
        if isinstance(capability, Capability)
        else Capability(capability)
        for capability in required_capabilities
    }

    def _require_capabilities(current_user: User = Depends(get_current_user)) -> User:
        granted = get_user_capabilities(current_user.role)
        if not required.issubset(granted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _require_capabilities


def get_current_user_org_ids(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[uuid.UUID]:
    """Return org IDs for the current user and require at least one membership."""
    org_ids = get_user_org_ids(db, current_user.id)
    if not org_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    return org_ids


def get_current_user_primary_org_id(
    org_ids: list[uuid.UUID] = Depends(get_current_user_org_ids),
) -> uuid.UUID:
    """Return the first org ID for the current user."""
    return org_ids[0]


def enforce_resource_org_ownership(
    resource_org_id: uuid.UUID | None,
    member_org_ids: list[uuid.UUID],
) -> None:
    """Raise 403 if a resource does not belong to one of the caller's orgs."""
    if resource_org_id is None or resource_org_id not in member_org_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
