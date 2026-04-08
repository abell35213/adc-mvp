"""Auth API routes — login, register, logout, and me."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    MeResponse,
    LogoutResponse,
)
from app.audit.emitter import emit_audit_event
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.logging import set_log_context
from app.core.metrics import MetricNames, increment, timed
from app.core.security import decode_access_token, hash_password, verify_password, create_access_token
from app.db.models import Event, Org, User
from app.db.repo.users import (
    create_org,
    create_user,
    get_user_by_email,
    get_user_org_ids,
    link_user_org,
)
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.security.csrf import CSRF_COOKIE_NAME, issue_csrf_token, validate_csrf_request
from app.security.permissions import Role, get_user_capabilities, normalize_role
from app.security.session import create_session, revoke_session, rotate_refresh_token

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_mfa_required(user: User, org_admin_mfa_required: bool) -> bool:
    role = normalize_role(user.role)
    if role == Role.SYSTEM_ADMIN:
        return True
    if role == Role.ORG_ADMIN:
        return org_admin_mfa_required
    return False


def _record_mfa_event(
    db: Session,
    *,
    user: User,
    event_type: SystemEventType,
    org_id: uuid.UUID | None,
    payload: dict | None = None,
) -> None:
    db.add(
        Event(
            org_id=org_id,
            incident_id=None,
            event_type=event_type.value,
            actor_type="user",
            actor_id=str(user.id),
            payload=payload or {},
        )
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    increment(MetricNames.AUTH_LOGIN_ATTEMPTS)
    with timed(MetricNames.AUTH_LOGIN_ATTEMPTS):
        user = get_user_by_email(db, body.email)

        if not user or not verify_password(body.password, user.password_hash):
            increment(MetricNames.AUTH_LOGIN_FAILURES)
            logger.warning("Login failed for email", extra={"email": body.email})
            org_ids = get_user_org_ids(db, user.id) if user else []
            emit_audit_event(
                db,
                org_id=org_ids[0] if org_ids else None,
                actor_type="user" if user else "anonymous",
                actor_id=str(user.id) if user else body.email.lower(),
                action="auth.login",
                event_type="auth_login_failed",
                outcome="failure",
                metadata={"reason": "invalid_credentials", "should_log": True},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            increment(MetricNames.AUTH_LOGIN_FAILURES)
            org_ids = get_user_org_ids(db, user.id)
            emit_audit_event(
                db,
                org_id=org_ids[0] if org_ids else None,
                actor_type="user",
                actor_id=str(user.id),
                action="auth.login",
                event_type="auth_login_failed",
                outcome="failure",
                metadata={"reason": "inactive_account", "should_log": True},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )

        org_ids = get_user_org_ids(db, user.id)
        org_admin_mfa_required = settings.ORG_ADMIN_MFA_REQUIRED
        if org_ids:
            org_rows = db.query(Org).filter(Org.id.in_(org_ids)).all()
            if any(org.require_org_admin_mfa for org in org_rows):
                org_admin_mfa_required = True

        mfa_required = _is_mfa_required(user, org_admin_mfa_required)
        if mfa_required and not user.mfa_enabled:
            increment(MetricNames.AUTH_LOGIN_FAILURES)
            emit_audit_event(
                db,
                org_id=org_ids[0] if org_ids else None,
                actor_type="user",
                actor_id=str(user.id),
                action="auth.login",
                event_type="auth_login_failed",
                outcome="failure",
                metadata={"reason": "mfa_enrollment_required", "should_log": True},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA enrollment required",
            )
        if mfa_required:
            if body.mfa_code is None:
                user.mfa_last_challenged_at_utc = datetime.now(timezone.utc)
                _record_mfa_event(
                    db,
                    user=user,
                    event_type=SystemEventType.MFA_CHALLENGE_COMPLETED,
                    org_id=org_ids[0] if org_ids else None,
                    payload={"status": "prompted"},
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="MFA code required",
                )
            expected_code = str(user.id.int)[-6:]
            if body.mfa_code != expected_code:
                increment(MetricNames.AUTH_LOGIN_FAILURES)
                emit_audit_event(
                    db,
                    org_id=org_ids[0] if org_ids else None,
                    actor_type="user",
                    actor_id=str(user.id),
                    action="auth.login",
                    event_type="auth_login_failed",
                    outcome="failure",
                    metadata={"reason": "invalid_mfa_code", "should_log": True},
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code",
                )
            user.mfa_last_challenged_at_utc = datetime.now(timezone.utc)
            _record_mfa_event(
                db,
                user=user,
                event_type=SystemEventType.MFA_CHALLENGE_COMPLETED,
                org_id=org_ids[0] if org_ids else None,
                payload={"status": "verified"},
            )
            db.commit()

        set_log_context(
            user_id=str(user.id), org_id=str(org_ids[0]) if org_ids else None
        )
        access_token, refresh_token, _session_id = create_session(
            db,
            user_id=user.id,
            org_id=org_ids[0] if org_ids else None,
            client_type="web",
            device_descriptor=request.headers.get("user-agent"),
            token_subject=str(user.id),
            token_claims={"role": normalize_role(user.role).value},
        )
        emit_audit_event(
            db,
            org_id=org_ids[0] if org_ids else None,
            actor_type="user",
            actor_id=str(user.id),
            action="auth.login",
            event_type="auth_login_succeeded",
            outcome="success",
            metadata={"role": normalize_role(user.role).value},
        )

    csrf_token = issue_csrf_token()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return LoginResponse(
        access_token=access_token,
        role=normalize_role(user.role).value,
        capabilities=sorted(cap.value for cap in get_user_capabilities(user.role)),
    )


@router.post("/mfa/enroll", status_code=204)
def enroll_mfa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_ids = get_user_org_ids(db, current_user.id)
    current_user.mfa_enabled = True
    current_user.mfa_enrolled_at_utc = datetime.now(timezone.utc)
    current_user.mfa_disabled_at_utc = None
    _record_mfa_event(
        db,
        user=current_user,
        event_type=SystemEventType.MFA_ENROLLMENT_COMPLETED,
        org_id=org_ids[0] if org_ids else None,
    )
    db.commit()
    return Response(status_code=204)


@router.post("/mfa/disable", status_code=204)
def disable_mfa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_ids = get_user_org_ids(db, current_user.id)
    current_user.mfa_enabled = False
    current_user.mfa_disabled_at_utc = datetime.now(timezone.utc)
    _record_mfa_event(
        db,
        user=current_user,
        event_type=SystemEventType.MFA_DISABLED,
        org_id=org_ids[0] if org_ids else None,
    )
    db.commit()
    return Response(status_code=204)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    validate_csrf_request(request)
    refresh_cookie = request.cookies.get("refresh_token")
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    access_token, next_refresh, _sid = rotate_refresh_token(
        db,
        refresh_token_value=refresh_cookie,
        token_subject="",
        token_claims={},
        expected_client_type="web",
        expected_device_descriptor=request.headers.get("user-agent"),
    )
    payload = decode_access_token(access_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issuance failed")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issuance failed")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token = create_access_token(
        {
            "sub": str(user.id),
            "sid": payload.get("sid"),
            "typ": "access",
            "role": normalize_role(user.role).value,
        }
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=next_refresh,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.cookie_samesite,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return RefreshResponse(access_token=token)


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    increment(MetricNames.AUTH_REGISTER_ATTEMPTS)
    with timed(MetricNames.AUTH_REGISTER_ATTEMPTS):
        existing = get_user_by_email(db, body.email)
        if existing:
            increment(MetricNames.AUTH_REGISTER_FAILURES)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        pw_hash = hash_password(body.password)
        user = create_user(
            db,
            email=body.email,
            password_hash=pw_hash,
            role=normalize_role(body.role).value,
        )

        org = create_org(db, name=body.org_name)
        link_user_org(db, user_id=user.id, org_id=org.id)

        set_log_context(user_id=str(user.id), org_id=str(org.id))
        token = create_access_token(
            {"sub": str(user.id), "role": normalize_role(user.role).value}
        )

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        role=normalize_role(user.role).value,
        capabilities=sorted(cap.value for cap in get_user_capabilities(user.role)),
        org_id=org.id,
        access_token=token,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response, current_user: User = Depends(get_current_user), request: Request = None, db: Session = Depends(get_db)):
    if request is not None:
        validate_csrf_request(request)
    token = request.cookies.get("access_token") if request else None
    sid = None
    if token:
        payload = decode_access_token(token)
        sid = payload.get("sid") if payload else None
    if sid:
        revoke_session(db, uuid.UUID(sid))

    response.delete_cookie(
        key="access_token", httponly=settings.COOKIE_HTTPONLY, secure=settings.COOKIE_SECURE, samesite=settings.cookie_samesite
    )
    response.delete_cookie(
        key="refresh_token", httponly=settings.COOKIE_HTTPONLY, secure=settings.COOKIE_SECURE, samesite=settings.cookie_samesite
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME, httponly=False, secure=settings.COOKIE_SECURE, samesite=settings.cookie_samesite
    )
    set_log_context(user_id=str(current_user.id))
    return LogoutResponse()


@router.get("/me", response_model=MeResponse)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_ids = get_user_org_ids(db, current_user.id)
    set_log_context(
        user_id=str(current_user.id), org_id=str(org_ids[0]) if org_ids else None
    )
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        role=normalize_role(current_user.role).value,
        capabilities=sorted(
            cap.value for cap in get_user_capabilities(current_user.role)
        ),
        org_ids=org_ids,
        active_org_id=org_ids[0] if org_ids else None,
    )
