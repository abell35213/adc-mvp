"""Authentication context helpers + identity provider abstraction layer."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

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


@dataclass(frozen=True)
class IdentityPrincipal:
    """Normalized principal produced by an external IdP strategy."""

    subject: str
    email: str | None
    display_name: str | None
    provider: str
    claims: dict[str, Any]


@dataclass(frozen=True)
class IdentityAuthResult:
    """Result of exchanging/asserting external identity credentials."""

    principal: IdentityPrincipal
    raw_token: str | None = None


class IdentityProviderStrategy(Protocol):
    """Pluggable strategy contract for external auth providers (OIDC / SAML)."""

    provider_name: str

    def begin_auth(self, *, relay_state: str | None = None) -> str:
        """Return provider redirect URL to initiate authentication."""

    def complete_auth(self, *, payload: dict[str, Any]) -> IdentityAuthResult:
        """Validate provider callback payload and return normalized identity."""


class IdentityProviderRegistry:
    """In-process registry for auth provider strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, IdentityProviderStrategy] = {}

    def register(self, strategy: IdentityProviderStrategy) -> None:
        key = strategy.provider_name.strip().lower()
        if not key:
            raise ValueError("Identity provider strategy must define provider_name")
        self._strategies[key] = strategy

    def resolve(self, provider_name: str) -> IdentityProviderStrategy:
        key = provider_name.strip().lower()
        if key not in self._strategies:
            raise KeyError(f"Unknown identity provider: {provider_name}")
        return self._strategies[key]


class OIDCIdentityProviderStrategy:
    """Base hook points for OIDC provider integrations."""

    provider_name = "oidc"

    def begin_auth(self, *, relay_state: str | None = None) -> str:
        raise NotImplementedError("OIDC begin_auth hook must be implemented")

    def complete_auth(self, *, payload: dict[str, Any]) -> IdentityAuthResult:
        raise NotImplementedError("OIDC complete_auth hook must be implemented")


class SAMLIdentityProviderStrategy:
    """Base hook points for SAML provider integrations."""

    provider_name = "saml"

    def begin_auth(self, *, relay_state: str | None = None) -> str:
        raise NotImplementedError("SAML begin_auth hook must be implemented")

    def complete_auth(self, *, payload: dict[str, Any]) -> IdentityAuthResult:
        raise NotImplementedError("SAML complete_auth hook must be implemented")


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
