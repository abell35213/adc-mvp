"""Driver OTP authentication routes."""

import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverOtpRequest,
    DriverOtpRequestResponse,
    DriverOtpVerifyRequest,
    DriverOtpVerifyResponse,
    DriverTokenRefreshRequest,
    DriverSessionRevokeRequest,
)
from app.audit.emitter import emit_audit_event
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.repo.drivers import (
    create_otp_challenge,
    get_driver_by_phone,
    get_latest_otp_challenge_by_phone,
    increment_otp_attempts,
    mark_otp_verified,
)
from app.db.repo.message_operations import create_message_operation, update_message_operation_status
from app.db.session import get_db
from app.integrations.errors import as_normalized_error
from app.security.session import create_session, revoke_session, rotate_refresh_token
from app.services.phone_normalize import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter()
_REQUEST_LIMIT = settings.OTP_REQUEST_RATE_LIMIT
_VERIFY_LIMIT = settings.OTP_VERIFY_RATE_LIMIT
_RATE_LIMIT_WINDOW_SECONDS = settings.OTP_RATE_LIMIT_WINDOW_SECONDS

_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max_calls = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local current = redis.call('ZCARD', key)
if current >= max_calls then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if oldest[2] then
        retry_after = math.ceil((tonumber(oldest[2]) + window_ms - now_ms) / 1000)
        if retry_after < 1 then
            retry_after = 1
        end
    end
    return {0, retry_after}
end

local request_id = tostring(now_ms) .. '-' .. tostring(redis.call('INCR', key .. ':seq'))
redis.call('ZADD', key, now_ms, request_id)
local ttl_seconds = math.ceil(window_ms / 1000)
redis.call('EXPIRE', key, ttl_seconds)
redis.call('EXPIRE', key .. ':seq', ttl_seconds)
return {1, 0}
"""

_rate_limit_script_sha: str | None = None
_redis_client: redis.Redis | None = None


def _phone_hash(phone_e164: str) -> str:
    """Return a keyed HMAC-SHA256 hex digest of the phone number for audit logs."""
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        phone_e164.encode(),
        hashlib.sha256,
    ).hexdigest()


def _get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_client


def _rate_limit_redis_key(bucket_name: str, phone_e164: str) -> str:
    return f"otp:ratelimit:{bucket_name}:{_phone_hash(phone_e164)}:{_RATE_LIMIT_WINDOW_SECONDS}s"


def _run_rate_limit_script(redis_client: redis.Redis, redis_key: str, max_calls: int):
    global _rate_limit_script_sha
    now_ms = int(time.time() * 1000)
    window_ms = _RATE_LIMIT_WINDOW_SECONDS * 1000
    args = [now_ms, window_ms, max_calls]
    if _rate_limit_script_sha is None:
        _rate_limit_script_sha = redis_client.script_load(_RATE_LIMIT_SCRIPT)
    try:
        return redis_client.evalsha(_rate_limit_script_sha, 1, redis_key, *args)
    except redis.exceptions.NoScriptError:
        _rate_limit_script_sha = redis_client.script_load(_RATE_LIMIT_SCRIPT)
        return redis_client.evalsha(_rate_limit_script_sha, 1, redis_key, *args)


def _enforce_rate_limit(bucket_name: str, phone_e164: str, max_calls: int):
    redis_client = _get_redis_client()
    allowed, retry_after = _run_rate_limit_script(
        redis_client,
        _rate_limit_redis_key(bucket_name, phone_e164),
        max_calls,
    )
    if int(allowed) == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP attempts. Please retry later.",
            headers={"Retry-After": str(int(retry_after))},
        )


@router.post("/request-otp", response_model=DriverOtpRequestResponse)
def request_otp(body: DriverOtpRequest, db: Session = Depends(get_db)):
    try:
        phone_e164 = normalize_phone(body.phone_e164)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid phone number",
        )
    _enforce_rate_limit("request", phone_e164, _REQUEST_LIMIT)

    msg_op = create_message_operation(
        db,
        org_id=None,
        provider="twilio",
        domain="auth",
        purpose="otp_request",
        to_e164=phone_e164,
        status="queued",
        payload_json={"flow": "driver_auth"},
    )
    twilio_sid: str | None = None
    try:
        from app.services import twilio_verify

        twilio_sid = twilio_verify.start_verification(phone_e164)
        update_message_operation_status(
            db,
            msg_op,
            to_status="sent",
            provider_message_id=twilio_sid,
            details_json={"verify_sid": twilio_sid},
        )
    except Exception as exc:
        normalized_error = as_normalized_error(exc, provider_hint="twilio", category="auth")
        update_message_operation_status(
            db,
            msg_op,
            to_status="failed",
            normalized_error_code=normalized_error.code,
            details_json={"reason": "twilio_verify_start_failed"},
        )
        logger.warning(
            "Twilio verify start failed for phone hash=%s", _phone_hash(phone_e164)
        )

    challenge = create_otp_challenge(db, phone_e164, twilio_sid=twilio_sid)

    logger.info(
        "DRIVER_OTP_REQUESTED phone_hash=%s challenge=%s",
        _phone_hash(phone_e164),
        challenge.challenge_id,
    )

    return DriverOtpRequestResponse()


@router.post("/verify-otp", response_model=DriverOtpVerifyResponse)
def verify_otp(body: DriverOtpVerifyRequest, db: Session = Depends(get_db)):
    try:
        phone_e164 = normalize_phone(body.phone_e164)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid phone number",
        )
    _enforce_rate_limit("verify", phone_e164, _VERIFY_LIMIT)
    verify_operation = create_message_operation(
        db,
        org_id=None,
        provider="twilio",
        domain="auth",
        purpose="otp_verify",
        to_e164=phone_e164,
        status="queued",
        payload_json={"flow": "driver_auth"},
    )

    challenge = get_latest_otp_challenge_by_phone(db, phone_e164)
    if challenge is None:
        emit_audit_event(
            db,
            org_id=None,
            actor_type="driver_phone",
            actor_id=_phone_hash(phone_e164),
            action="auth.driver_login",
            event_type="driver_login_failed",
            outcome="failure",
            metadata={"reason": "challenge_not_found", "should_log": True},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    if challenge.status == "locked":
        emit_audit_event(
            db,
            org_id=None,
            actor_type="driver_phone",
            actor_id=_phone_hash(phone_e164),
            action="auth.driver_login",
            event_type="driver_login_failed",
            outcome="failure",
            metadata={"reason": "challenge_locked", "should_log": True},
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Challenge locked due to too many attempts",
        )

    if challenge.status == "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge already verified",
        )

    now = datetime.now(timezone.utc)
    if challenge.expires_at_utc.tzinfo is None:
        expires = challenge.expires_at_utc.replace(tzinfo=timezone.utc)
    else:
        expires = challenge.expires_at_utc
    if now > expires:
        challenge.status = "expired"
        db.commit()
        emit_audit_event(
            db,
            org_id=None,
            actor_type="driver_phone",
            actor_id=_phone_hash(phone_e164),
            action="auth.driver_login",
            event_type="driver_login_failed",
            outcome="failure",
            metadata={"reason": "challenge_expired", "should_log": True},
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Challenge expired",
        )

    otp_ok = False
    try:
        from app.services import twilio_verify

        otp_ok = twilio_verify.check_verification(phone_e164, body.otp_code)
    except Exception as exc:
        normalized_error = as_normalized_error(exc, provider_hint="twilio", category="auth")
        update_message_operation_status(
            db,
            verify_operation,
            to_status="failed",
            normalized_error_code=normalized_error.code,
            details_json={"reason": "twilio_verify_check_failed"},
        )
        logger.exception("Twilio verify check failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OTP verification service unavailable, please retry",
        )

    if not otp_ok:
        update_message_operation_status(
            db,
            verify_operation,
            to_status="undelivered",
            normalized_error_code="AUTH_INVALID_OTP",
            details_json={"reason": "invalid_otp"},
        )
        challenge = increment_otp_attempts(db, challenge)
        logger.info(
            "DRIVER_OTP_FAILED phone_hash=%s attempts=%d status=%s",
            _phone_hash(phone_e164),
            challenge.attempt_count,
            challenge.status,
        )
        if challenge.status == "locked":
            emit_audit_event(
                db,
                org_id=None,
                actor_type="driver_phone",
                actor_id=_phone_hash(phone_e164),
                action="auth.driver_login",
                event_type="driver_login_failed",
                outcome="failure",
                metadata={"reason": "otp_locked", "attempt_count": challenge.attempt_count, "should_log": True},
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Challenge locked due to too many attempts",
            )
        emit_audit_event(
            db,
            org_id=None,
            actor_type="driver_phone",
            actor_id=_phone_hash(phone_e164),
            action="auth.driver_login",
            event_type="driver_login_failed",
            outcome="failure",
            metadata={"reason": "invalid_otp", "attempt_count": challenge.attempt_count, "should_log": True},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP",
        )
    update_message_operation_status(
        db,
        verify_operation,
        to_status="delivered",
        details_json={"reason": "otp_approved"},
    )

    driver = get_driver_by_phone(db, phone_e164)
    if driver is None:
        emit_audit_event(
            db,
            org_id=None,
            actor_type="driver_phone",
            actor_id=_phone_hash(phone_e164),
            action="auth.driver_login",
            event_type="driver_login_failed",
            outcome="failure",
            metadata={"reason": "unknown_driver", "should_log": True},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No driver registered with this phone number",
        )
    mark_otp_verified(db, challenge)

    access_token, refresh_token, _sid = create_session(
        db,
        user_id=None,
        org_id=driver.org_id,
        client_type="driver_mobile",
        device_descriptor=body.device_descriptor,
        token_subject=str(driver.driver_id),
        token_claims={
            "scope": "driver",
            "phone": driver.phone_e164,
        },
    )

    logger.info(
        "DRIVER_OTP_VERIFIED phone_hash=%s driver=%s",
        _phone_hash(phone_e164),
        driver.driver_id,
    )
    emit_audit_event(
        db,
        org_id=driver.org_id,
        actor_type="driver",
        actor_id=str(driver.driver_id),
        action="auth.driver_login",
        event_type="driver_login_succeeded",
        outcome="success",
        metadata={"phone_hash": _phone_hash(phone_e164)},
    )

    return DriverOtpVerifyResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=DriverOtpVerifyResponse)
def refresh_driver_token(body: DriverTokenRefreshRequest, db: Session = Depends(get_db)):
    access_token, refresh_token, _session_id = rotate_refresh_token(
        db,
        refresh_token_value=body.refresh_token,
        token_subject="",
        token_claims={"scope": "driver"},
        expected_client_type="driver_mobile",
        expected_device_descriptor=body.device_descriptor,
    )

    payload = decode_access_token(access_token)
    if payload is None or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issuance failed")

    return DriverOtpVerifyResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/revoke")
def revoke_driver_session(body: DriverSessionRevokeRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    from app.db.models import RefreshToken

    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    revoke_session(db, uuid.UUID(str(row.session_id)))
    return {"detail": "Session revoked"}
