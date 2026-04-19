"""Expansion planning state definitions and helpers."""

from __future__ import annotations

from typing import Literal

ExpansionReadiness = Literal[
    "not_started",
    "planning",
    "pilot_ready",
    "scale_ready",
    "blocked",
]

EXPANSION_READINESS_STATES: tuple[ExpansionReadiness, ...] = (
    "not_started",
    "planning",
    "pilot_ready",
    "scale_ready",
    "blocked",
)

EXPANSION_FEATURES: tuple[str, ...] = (
    "expansion.scorecard",
    "expansion.rollout",
)
