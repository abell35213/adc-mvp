"""Auth API routes — login, register, logout, and me."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    MeResponse,
    LogoutResponse,
)
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.logging import set_log_context
from app.core.metrics import MetricNames, increment, timed
from app.core.security import hash_password, verify_password, create_access_token
from app.db.models import User
from app.db.repo.users import (
    create_org,
    create_user,
    get_user_by_email,
    get_user_org_ids,
    link_user_org,
)
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    increment(MetricNames.AUTH_LOGIN_ATTEMPTS)
    with timed(MetricNames.AUTH_LOGIN_ATTEMPTS):
        user = get_user_by_email(db, body.email)

        if not user or not verify_password(body.password, user.password_hash):
            increment(MetricNames.AUTH_LOGIN_FAILURES)
            logger.warning("Login failed for email", extra={"email": body.email})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            increment(MetricNames.AUTH_LOGIN_FAILURES)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )

        org_ids = get_user_org_ids(db, user.id)
        set_log_context(
            user_id=str(user.id), org_id=str(org_ids[0]) if org_ids else None
        )
        token = create_access_token({"sub": str(user.id), "role": user.role})

    # Set httpOnly cookie for browser-based dashboard access
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=30 * 60,
    )

    return LoginResponse(access_token=token, role=user.role)


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
        user = create_user(db, email=body.email, password_hash=pw_hash, role=body.role)

        # Auto-create org and link
        org = create_org(db, name=body.org_name)
        link_user_org(db, user_id=user.id, org_id=org.id)

        set_log_context(user_id=str(user.id), org_id=str(org.id))
        token = create_access_token({"sub": str(user.id), "role": user.role})

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        org_id=org.id,
        access_token=token,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response, current_user: User = Depends(get_current_user)):
    # Stateless JWT — the client discards the token.
    # Clear the httpOnly cookie as well.
    response.delete_cookie(
        key="access_token", httponly=True, secure=settings.COOKIE_SECURE, samesite="lax"
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
        role=current_user.role,
        org_ids=org_ids,
        active_org_id=org_ids[0] if org_ids else None,
    )
