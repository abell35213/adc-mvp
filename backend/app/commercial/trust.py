"""Trust and deployment scope state definitions."""

from __future__ import annotations

from typing import Literal

DeploymentScope = Literal[
    "single_site",
    "multi_site",
    "regional",
    "national",
    "global",
]

DEPLOYMENT_SCOPE_STATES: tuple[DeploymentScope, ...] = (
    "single_site",
    "multi_site",
    "regional",
    "national",
    "global",
)

TRUST_FEATURES: tuple[str, ...] = (
    "trust.sso",
    "trust.audit_controls",
)
