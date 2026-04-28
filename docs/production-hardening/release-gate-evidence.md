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

## 4) Accepted residual dependency advisories

These advisories are accepted with explicit risk justification and tracked to the next ecosystem upgrade window. Required CI gates (`pip-audit`, `npm audit --audit-level=high`) remain enforced — these residuals are at `low`/`moderate` severity only.

### 4.1 `frontend/` (Next.js 16)

| Package | Severity | Source / advisory | Justification | Tracked remediation |
| --- | --- | --- | --- | --- |
| `postcss@8.4.31` | moderate | [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93) | Bundled by `next@16.2.4` under `node_modules/next/node_modules/postcss`; not exposed in `frontend/`'s own build pipeline (top-level `postcss` is `>=8.5.10`). No high/critical exposure surface in our SSR/SSG output. | Tracked to next Next.js minor that bumps the bundled `postcss`. |

### 4.2 `driver-app/` (Expo SDK 54)

After `npm audit fix`, **0 high / 0 critical** advisories remain. The residual `low`/`moderate` advisories below all ride along Expo CLI / build-time tooling and cannot be patched without an Expo SDK upgrade.

| Package | Severity | Reaches runtime? | Justification |
| --- | --- | --- | --- |
| `@tootallnate/once`, `http-proxy-agent`, `jest-environment-jsdom`, `jsdom` | low | No (test/dev only) | Pulled in by `jest-environment-jsdom` for the rntl Jest project; not bundled into the production driver app. |
| `@expo/cli`, `@expo/config`, `@expo/config-plugins`, `@expo/metro-config`, `@expo/prebuild-config`, `xcode` | moderate | No (build-time only) | Expo CLI build chain. Used during `expo start` / `expo prebuild` on developer machines and CI build agents; never shipped to devices. |
| `brace-expansion` ([GHSA-f886-m6hf-6m8v](https://github.com/advisories/GHSA-f886-m6hf-6m8v)) | moderate | No | Transitive of `glob`/`minimatch` under Expo CLI; not on the runtime path. |
| `expo`, `expo-asset`, `expo-constants` | moderate | Yes (limited) | Pinned by Expo SDK 54 bundledNativeModules. Mitigated by upcoming Expo SDK upgrade window; advisories are denial-of-service / parsing edge cases, not RCE/credential paths. |
| `jest-expo` | moderate | No (test only) | Test runner preset. |
| `postcss` ([GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93)) | moderate | No | Build-time CSS pipeline used by Expo web preview only. |
| `uuid` ([GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq)) | moderate | Yes (indirect) | Used by Expo internals; advisory is around predictable RNG seeding for v4 in obsolete versions. Driver app does not rely on `uuid` for any security-relevant identifier (sessions/tokens are server-issued). |

**Tracked remediation:** all `driver-app` Expo-CLI residuals close on the next Expo SDK upgrade. A reminder issue is filed against each Expo SDK release window.

**Re-validation cadence:** `dependency-vulnerability-scan` job in `.github/workflows/ci.yml` runs on every PR and main push at `--audit-level=critical`; the Phase 1 exit criterion (`--audit-level=high` clean for both `frontend` and `driver-app`) is currently met.
