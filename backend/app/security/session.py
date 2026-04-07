"""Session and refresh token lifecycle helpers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import RefreshToken, SessionRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _new_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def create_session(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    org_id: uuid.UUID | None,
    client_type: str,
    device_descriptor: str | None,
    token_subject: str,
    token_claims: dict,
) -> tuple[str, str, uuid.UUID]:
    now = _utcnow()
    session_id = uuid.uuid4()
    refresh_family_id = uuid.uuid4()

    session = SessionRecord(
        session_id=session_id,
        user_id=user_id,
        org_id=org_id,
        client_type=client_type,
        device_descriptor=device_descriptor,
        created_at=now,
        last_seen_at=now,
        refresh_family_id=refresh_family_id,
    )
    db.add(session)

    refresh_token_value = _new_refresh_token_value()
    refresh_row = RefreshToken(
        token_id=uuid.uuid4(),
        session_id=session_id,
        refresh_family_id=refresh_family_id,
        token_hash=_hash_refresh_token(refresh_token_value),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_row)
    db.commit()

    access_token = create_access_token(
        {
            "sub": token_subject,
            "sid": str(session_id),
            "typ": "access",
            **token_claims,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return access_token, refresh_token_value, session_id


def validate_session(
    db: Session,
    *,
    session_id: uuid.UUID,
    expected_client_type: str | None = None,
    expected_device_descriptor: str | None = None,
) -> SessionRecord:
    session = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if session is None or session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
    if expected_client_type and session.client_type != expected_client_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session client mismatch")
    if expected_device_descriptor and session.device_descriptor != expected_device_descriptor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session device mismatch")

    session.last_seen_at = _utcnow()
    db.commit()
    return session


def rotate_refresh_token(
    db: Session,
    *,
    refresh_token_value: str,
    token_subject: str,
    token_claims: dict,
    expected_client_type: str | None = None,
    expected_device_descriptor: str | None = None,
) -> tuple[str, str, uuid.UUID]:
    now = _utcnow()
    token_hash = _hash_refresh_token(refresh_token_value)

    token_row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )
    if token_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if token_row.revoked_at is not None or token_row.consumed_at is not None:
        revoke_session(db, token_row.session_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token already used")

    if token_row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    session = validate_session(
        db,
        session_id=token_row.session_id,
        expected_client_type=expected_client_type,
        expected_device_descriptor=expected_device_descriptor,
    )

    token_row.consumed_at = now
    new_refresh_value = _new_refresh_token_value()
    new_refresh_row = RefreshToken(
        token_id=uuid.uuid4(),
        session_id=session.session_id,
        refresh_family_id=session.refresh_family_id,
        parent_token_id=token_row.token_id,
        token_hash=_hash_refresh_token(new_refresh_value),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_refresh_row)
    db.commit()

    subject = token_subject or (str(session.user_id) if session.user_id else "")
    access_token = create_access_token(
        {
            "sub": subject,
            "sid": str(session.session_id),
            "typ": "access",
            **token_claims,
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return access_token, new_refresh_value, session.session_id


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    now = _utcnow()
    session = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if session is None:
        return
    session.revoked_at = now
    (
        db.query(RefreshToken)
        .filter(RefreshToken.session_id == session_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )
    db.commit()
