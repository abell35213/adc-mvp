"""Blocker classification for onboarding readiness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.onboarding.models import ReadinessBlocker
from app.onboarding.progress import OnboardingSignals

BlockerSeverity = Literal["critical", "important"]


@dataclass(slots=True)
class ClassifiedBlocker:
    code: str
    title: str
    detail: str
    severity: BlockerSeverity
    blocking_step_key: str

    def to_model(self) -> ReadinessBlocker:
        return ReadinessBlocker(
            code=self.code,
            title=self.title,
            detail=self.detail,
            severity="error" if self.severity == "critical" else "warning",
            blocking_step_key=self.blocking_step_key,
            created_at_utc=datetime.now(timezone.utc),
            is_resolved=False,
        )


def classify_blockers(*, signals: OnboardingSignals) -> list[ClassifiedBlocker]:
    """Classify onboarding blockers into critical/important severity buckets."""
    blockers: list[ClassifiedBlocker] = []

    if not signals.org_settings_configured:
        blockers.append(
            ClassifiedBlocker(
                code="org_settings_incomplete",
                title="Organization settings incomplete",
                detail="Configure communication and safety contact settings before rollout.",
                severity="critical",
                blocking_step_key="org_settings",
            )
        )

    if signals.org_admin_count == 0:
        blockers.append(
            ClassifiedBlocker(
                code="org_admin_missing",
                title="Organization admin missing",
                detail="At least one org_admin account is required to administer launch settings.",
                severity="critical",
                blocking_step_key="users_roles",
            )
        )

    if signals.successful_import_count == 0:
        blockers.append(
            ClassifiedBlocker(
                code="imports_missing",
                title="No successful import",
                detail="Run and complete at least one source data import.",
                severity="critical",
                blocking_step_key="imports",
            )
        )
    elif signals.failed_import_count > 0:
        blockers.append(
            ClassifiedBlocker(
                code="imports_with_failures",
                title="Import failures detected",
                detail="One or more import jobs failed and must be remediated.",
                severity="important",
                blocking_step_key="imports",
            )
        )

    if signals.mapping_count == 0:
        blockers.append(
            ClassifiedBlocker(
                code="mappings_missing",
                title="Mappings incomplete",
                detail="External mappings are required for synced entities.",
                severity="important",
                blocking_step_key="mappings",
            )
        )

    if signals.active_integration_count == 0:
        blockers.append(
            ClassifiedBlocker(
                code="integrations_inactive",
                title="No active integrations",
                detail="Activate at least one integration connection.",
                severity="critical",
                blocking_step_key="integrations",
            )
        )

    if (
        signals.vehicles_total > 0
        and signals.qr_codes_activated < signals.vehicles_total
    ):
        blockers.append(
            ClassifiedBlocker(
                code="vehicle_qr_incomplete",
                title="Vehicle QR rollout incomplete",
                detail="Generate and activate QR tokens for all active vehicles.",
                severity="important",
                blocking_step_key="vehicle_qr",
            )
        )

    if not signals.protocol_configured:
        blockers.append(
            ClassifiedBlocker(
                code="driver_protocol_missing",
                title="Driver protocol not configured",
                detail="Enable driver acknowledgement workflow and publish instruction steps.",
                severity="critical",
                blocking_step_key="driver_protocol",
            )
        )

    if not signals.test_run_passed:
        blockers.append(
            ClassifiedBlocker(
                code="test_run_missing",
                title="Test run not completed",
                detail="Complete a successful test incident run before go-live.",
                severity="critical",
                blocking_step_key="test_run",
            )
        )

    if not signals.export_validation_passed:
        blockers.append(
            ClassifiedBlocker(
                code="export_validation_failed",
                title="Export validation failed",
                detail="Export pipeline must produce a ready package without failures.",
                severity="critical",
                blocking_step_key="export_validation",
            )
        )

    return blockers


def blocked_step_keys(blockers: list[ClassifiedBlocker]) -> set[str]:
    return {
        blocker.blocking_step_key
        for blocker in blockers
        if blocker.severity == "critical"
    }
