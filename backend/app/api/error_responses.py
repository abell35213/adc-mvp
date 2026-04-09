"""Helpers for standardized user-safe API error responses."""

from __future__ import annotations

from fastapi import HTTPException

from app.api.schemas import ApiErrorDetail, ApiErrorCode
from app.core.logging import get_request_id


def raise_api_error(
    *,
    status_code: int,
    message: str,
    code: ApiErrorCode,
    retry_hint: str | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=ApiErrorDetail(
            message=message,
            code=code,
            retry_hint=retry_hint,
            correlation_id=get_request_id(),
        ).model_dump(exclude_none=True),
    )
