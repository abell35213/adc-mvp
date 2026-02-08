"""Auth API routes — login and register."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse
from app.core.auth import hash_password, verify_password, create_access_token
from app.db.session import get_db
from app.db.repo_users import get_user_by_email, create_user, link_user_org
from app.db.repo_users import create_org

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return LoginResponse(access_token=token, role=user.role)


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    pw_hash = hash_password(body.password)
    user = create_user(db, email=body.email, password_hash=pw_hash, role=body.role)

    # Auto-create org and link
    org = create_org(db, name=body.org_name)
    link_user_org(db, user_id=user.id, org_id=org.id)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        org_id=org.id,
        access_token=token,
    )
