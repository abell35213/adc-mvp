# Guided Onboarding Test Matrix (API + UI Workflow + End-to-End)

This matrix defines executable coverage for onboarding readiness across CSV imports, integrations, QR deployment, and tenant-safety controls.

## 1) Acceptance criteria catalog

| ID | Acceptance criterion |
| --- | --- |
| ONB-AC-01 | Vehicle CSV import succeeds for valid payloads and reports accurate counters/outcomes. |
| ONB-AC-02 | Driver CSV import handles mixed valid/invalid rows and classifies failures without corrupting valid imports. |
| ONB-AC-03 | Duplicate rows in CSV import are surfaced as deterministic warnings/errors. |
| ONB-AC-04 | Incomplete readiness states are represented consistently (`not_started`, `in_progress`, `blocked`) before pilot/launch thresholds are met. |
| ONB-AC-05 | Integration validation failure modes (invalid credentials, partial support/mapping failures, repeated failures) are captured and surfaced with remediation context. |
| ONB-AC-06 | QR generation, bulk generation, printable output, and token rotation are correct and auditable. |
| ONB-AC-07 | Test-run records are isolated per org and cannot leak across tenants. |
| ONB-AC-08 | Pilot vs launch readiness logic is deterministic and requires launch-only gates before `launch_ready`. |
| ONB-AC-09 | Org isolation and role-based permissions are enforced for onboarding write paths while allowing approved read paths. |
| ONB-AC-10 | Guided onboarding workflow (settings → imports → mappings/integrations → QR → test run → export validation) is executable end-to-end with release evidence. |

## 2) Release gate definitions

| Gate ID | Gate description | Release evidence expectation |
| --- | --- | --- |
| RG-ONB-API | API onboarding regression suite green. | All mapped `pytest` selectors pass in CI and are attached to release evidence. |
| RG-ONB-UI | UI workflow regression suite green. | Frontend `node --test` onboarding workflow suite passes and artifacts are attached. |
| RG-ONB-E2E | Guided onboarding dry-run succeeds. | End-to-end runbook execution + onboarding test-run/export-check evidence is recorded. |
| RG-ONB-SEC | Org isolation/permission checks green. | Authorization regression + onboarding permission tests pass with zero P0/P1 findings. |
| RG-ONB-GO | Go/No-Go decision can reference objective evidence. | `docs/production-hardening/release-gate-evidence.md` and release checklist are updated with the run IDs/results. |

## 3) Acceptance criteria → executable tests → release gates

| Acceptance criterion | API-level executable tests | UI workflow executable tests | End-to-end guided onboarding scenarios | Release gates |
| --- | --- | --- | --- | --- |
| ONB-AC-01 CSV success/failure counters | `backend/tests/test_api_endpoints.py::TestVehicleImportJobs::test_create_vehicle_import_job_and_read_results` | `frontend/tests/smoke.test.mjs` (workflow shell smoke for web test harness) | Scenario E2E-01: Upload vehicle CSV with required headers, verify `/org/onboarding/status` and job counters align. | RG-ONB-API, RG-ONB-UI, RG-ONB-E2E |
| ONB-AC-02 Driver CSV mixed outcomes | `backend/tests/test_api_endpoints.py::TestDriverImportJobs::test_create_driver_import_job_and_read_results` | `frontend/tests/smoke.test.mjs` (workflow shell smoke for web test harness) | Scenario E2E-02: Submit driver CSV containing invalid phone + missing fields; confirm expected warning/error buckets. | RG-ONB-API, RG-ONB-UI, RG-ONB-E2E |
| ONB-AC-03 Duplicate detection | `backend/tests/test_api_endpoints.py::TestDriverImportJobs::test_create_driver_import_job_and_read_results` (duplicate warning count), `backend/tests/test_api_endpoints.py::TestVehicleImportJobs::test_create_vehicle_import_job_and_read_results` (duplicate warning count) | `frontend/tests/smoke.test.mjs` (UI test harness smoke) | Scenario E2E-03: Re-import with duplicate identifiers; verify duplicate category in UI preview + API job summary. | RG-ONB-API, RG-ONB-UI, RG-ONB-E2E |
| ONB-AC-04 Incomplete readiness states | `backend/tests/test_onboarding_service.py::test_build_onboarding_readiness_uses_blocked_status_when_critical_exists`, `backend/tests/test_api_endpoints.py::TestOrgOnboardingAndSettings::test_onboarding_status_and_mark_step` | `frontend/tests/smoke.test.mjs` (UI route/workflow harness smoke) | Scenario E2E-04: Walk onboarding with missing prerequisites and validate status progression from `not_started` to `blocked`/`in_progress`. | RG-ONB-API, RG-ONB-UI, RG-ONB-E2E |
| ONB-AC-05 Integration failure modes | `backend/tests/test_api_endpoints.py::TestIntegrationDiagnosticsRoutes::test_integration_validate_requires_admin_role`, `backend/tests/test_api_endpoints.py::TestIntegrationDiagnosticsRoutes::test_integration_validation_results_endpoint_and_partial_support`, `backend/tests/test_onboarding_service.py::test_build_onboarding_readiness_metrics_and_alerts_for_ready_state` | `frontend/tests/smoke.test.mjs` (UI workflow harness smoke) | Scenario E2E-05: Validate integration in degraded state and confirm remediation messages in onboarding dashboard + audit trail. | RG-ONB-API, RG-ONB-E2E, RG-ONB-SEC |
| ONB-AC-06 QR generation/rotation | `backend/tests/test_api_endpoints.py::TestVehicleQrDeploymentEndpoints::test_generate_bulk_rotate_printable_and_stats`, `backend/tests/test_driver_admin_endpoints.py::TestDriverVehicleResolveQr::test_resolve_qr_returns_vehicle` | `frontend/tests/smoke.test.mjs` (UI workflow harness smoke) | Scenario E2E-06: Generate QR, rotate token, print PDF, verify coverage blockers clear once distributed. | RG-ONB-API, RG-ONB-E2E |
| ONB-AC-07 Test-run isolation | `backend/tests/test_api_endpoints.py::TestOrgOnboardingAndSettings::test_org_test_runs_crud_and_complete_step` | N/A (server-enforced) | Scenario E2E-07: Org A creates run; Org B cannot list/read that run ID. | RG-ONB-API, RG-ONB-SEC, RG-ONB-E2E |
| ONB-AC-08 Pilot vs launch logic | `backend/tests/test_onboarding_service.py::test_readiness_status_transitions_pilot_and_launch`, `backend/tests/test_onboarding_service.py::test_export_validation_override_does_not_bypass_successful_test_export_requirement` | `frontend/tests/exportFlowModel.test.mjs` (state transition workflow assertions) | Scenario E2E-08: Reach pilot prerequisites without export validation (expect `pilot_ready`), then pass export check (expect `launch_ready`). | RG-ONB-API, RG-ONB-UI, RG-ONB-E2E |
| ONB-AC-09 Org isolation/permissions | `backend/tests/test_authorization_regressions.py::test_phase6_import_write_denied_for_read_only`, `backend/tests/test_authorization_regressions.py::test_export_download_checks_org_membership`, `backend/tests/test_api_endpoints.py::TestIntegrationDiagnosticsRoutes::test_integration_operations_and_evidence_summary` | `frontend/tests/smoke.test.mjs` (UI role-gated flow harness smoke) | Scenario E2E-09: Validate read_only can view readiness but cannot mutate onboarding/import endpoints; validate cross-org diagnostics isolation. | RG-ONB-API, RG-ONB-UI, RG-ONB-SEC, RG-ONB-E2E |
| ONB-AC-10 Guided onboarding journey | `backend/tests/test_api_endpoints.py::TestOrgOnboardingAndSettings::test_org_settings_completion_rule_updates_onboarding_status`, `backend/tests/test_api_endpoints.py::TestOrgOnboardingAndSettings::test_export_check_action_endpoint` | `frontend/tests/exportFlowModel.test.mjs` + `frontend/tests/smoke.test.mjs` | Scenario E2E-10: Full dry run using onboarding dashboard and test-run/export-check endpoints; attach audit event IDs and readiness snapshot to release packet. | RG-ONB-API, RG-ONB-UI, RG-ONB-E2E, RG-ONB-GO |

## 4) Execution commands (release evidence snippets)

- API regression gate:
  - `cd backend && pytest tests/test_api_endpoints.py tests/test_onboarding_service.py tests/test_authorization_regressions.py tests/test_driver_admin_endpoints.py -v`
- UI workflow gate:
  - `cd frontend && npm test`
- Security/isolation gate:
  - `cd backend && pytest tests/test_authorization_regressions.py -v`
- Release governance cross-check:
  - `python scripts/check_release_hardening_gates.py`

## 5) Evidence package requirements per release

1. Test command outputs with commit SHA.
2. Onboarding readiness payload snapshots before/after guided run.
3. Audit event IDs for onboarding test run creation/completion and export validation run.
4. Explicit gate status for RG-ONB-API / RG-ONB-UI / RG-ONB-E2E / RG-ONB-SEC / RG-ONB-GO.
