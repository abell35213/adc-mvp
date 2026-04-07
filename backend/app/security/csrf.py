"""CSRF protection helpers for cookie-authenticated flows."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def issue_csrf_token() -> str:
    """Create a new CSRF token value for double-submit protection."""
    return secrets.token_urlsafe(32)


def requires_csrf_validation(request: Request) -> bool:
    """Return True when request is cookie-authenticated and mutating."""
    if request.method.upper() not in _MUTATING_METHODS:
        return False

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return False

    return bool(request.cookies.get("access_token") or request.cookies.get("refresh_token"))


def validate_csrf_request(request: Request) -> None:
    """Validate double-submit CSRF token for cookie-authenticated requests."""
    if not requires_csrf_validation(request):
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )

    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token invalid",
        )
