# Production onboarding release gate evidence

This document is the authoritative pre-onboarding proof that MVP and strong production-readiness controls are satisfied before enabling customer production traffic.

## 1) MVP acceptance criteria (must-pass)

| Gate | Acceptance criteria | Evidence artifact |
| --- | --- | --- |
| MVP functionality complete | Required backend endpoints, driver flows, and export generation paths are implemented and covered by automated tests. | `backend/tests/test_api_endpoints.py`, `backend/tests/test_driver_auth_endpoints.py`, `backend/tests/test_export_section23_acceptance.py` |
| Security baseline complete | AuthN/AuthZ boundaries, org isolation, session expiry, and export permissions are validated in CI. | `backend/tests/test_production_hardening_suite.py`, `backend/tests/test_authorization_regressions.py`, `backend/tests/test_auth.py` |
| Reliability baseline complete | Background processing retry/dead-letter behavior and storage outage degradation paths are validated. | `backend/tests/test_celery_tasks.py`, `backend/tests/test_production_hardening_suite.py`, `docs/reliability-and-incident-response-runbook.md` |
| Data governance complete | Data classes and required controls are documented and enforced by onboarding gate review. | `docs/security/data-classification.md` |

## 2) Strong production-readiness acceptance criteria (must-pass)

| Gate area | Strong criterion | Evidence artifact |
| --- | --- | --- |
| Identity and authorization | Least-privilege enforcement, tenancy boundaries, and denial telemetry are tested and reviewed. | `backend/tests/test_authorization_regressions.py`, `backend/tests/test_production_hardening_suite.py` |
| Audit and logging | Security-significant actions are auditable with actor/outcome correlation and retained per policy. | `backend/tests/test_audit_service.py`, `docs/release-readiness-checklist.md` |
| Observability and operations | Worker/API health, backlog, and failure signals are monitored with incident runbooks. | `docs/operations/dashboards/job-processing.md`, `docs/reliability-and-incident-response-runbook.md` |
| Backup/DR and outage handling | Recovery objectives and outage procedures are documented and drill-ready. | `docs/operations/backup-dr/README.md`, `docs/reliability-and-incident-response-runbook.md` |
| Release governance | Priority-1 production tags are blocked unless hardening gates are complete. | `scripts/check_release_hardening_gates.py`, `docs/production-hardening/checklist.yaml` |

## 3) Customer production onboarding decision rule

Customer production onboarding is permitted only when all conditions below are true:

1. All Priority-1 gates in `docs/production-hardening/checklist.yaml` are marked `complete`/`verified`.
2. Security and reliability suite (`backend/tests/test_production_hardening_suite.py`) passes in CI.
3. Release checklist sign-off is recorded with no unresolved No-Go owner.

If any condition is unmet, onboarding remains blocked.
