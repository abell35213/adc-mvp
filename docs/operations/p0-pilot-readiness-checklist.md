# P0 Pilot Readiness Checklist

Use this checklist for every controlled pilot release candidate. Keep statuses truthful and update the verification date whenever commands are rerun.

Status values: `Verified complete`, `Code-fixed; needs local Docker verification`, `Requires AWS/staging verification`, `Deferred beyond controlled pilot`.

## Controlled pilot blockers

| # | Checklist item | Status | Verification command | Notes | Files | Exit criteria |
|---|---|---|---|---|---|---|
| 1 | Frontend patched build path is the pilot path | Verified complete | `cd frontend && npm run build` | No GitHub Pages / static Next.js workflow exists in the repo. The active frontend path is the dynamic Next.js build used by Docker and CI. | `frontend/package.json`; `frontend/Dockerfile`; `.github/workflows/ci.yml` | Build succeeds on the patched Next.js release line and no stale Pages blocker remains in pilot docs. |
| 2 | Backend org-isolation export regression is pinned to the correct test id | Verified complete | `cd backend && APP_ENV=test pytest tests/test_api_endpoints.py::TestGetExport::test_get_export_forbidden_for_other_org -q` | Replaces the stale `TestExportEndpoints` class path. | `backend/tests/test_api_endpoints.py`; `docs/operations/p0-pilot-readiness-checklist.md` | The documented node id matches the real test and passes. |
| 3 | Backend tests use deterministic fake Redis in `APP_ENV=test` | Verified complete | `cd backend && APP_ENV=test pytest tests/test_driver_admin_endpoints.py -q --durations=20` | Test fixtures now force fake Redis for rate-limit code paths so suites do not resolve `test-redis.invalid` during unit/integration tests. | `backend/tests/conftest.py`; `backend/tests/helpers/fake_redis.py`; `backend/app/services/rate_limit_service.py`; `backend/app/api/routes_driver_auth.py` | Targeted driver/rate-limit suites pass without real Redis network attempts. |
| 4 | Full backend suite passes for the release candidate | Code-fixed; needs local Docker verification | `cd backend && APP_ENV=test pytest tests/ -q --durations=20` | Targeted suites pass in the agent environment; rerun the full suite locally for release evidence if timing limits recur here. | `backend/tests/`; `.github/workflows/ci.yml`; `Makefile` | Full suite completes cleanly and slowest tests are reviewed. |
| 5 | Unsafe PDF fail-open mode is blocked in staging/prod | Verified complete | `cd backend && APP_ENV=test pytest tests/test_config.py -q` | `PDF_RENDER_FAIL_OPEN=true` is now rejected outside `local` / `test`. | `backend/app/config/settings.py`; `backend/app/config/validation.py`; `backend/app/services/pdf_render.py`; `backend/tests/test_config.py` | Startup validation fails fast in staging/prod if fail-open rendering is enabled. |
| 6 | Raw client idempotency keys are not stored in workflow event payloads | Verified complete | `cd backend && APP_ENV=test pytest tests/test_incident_workflow_service.py tests/test_driver_admin_endpoints.py -q` | Driver-initiated workflow events retain only hashed/redacted idempotency metadata. | `backend/app/services/incident_workflow_service.py`; `backend/tests/test_incident_workflow_service.py`; `backend/tests/test_driver_admin_endpoints.py` | Events contain hashes only and duplicate-protection behavior remains intact. |
| 7 | Frontend lint/typecheck/test/build and audit are green | Verified complete | `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build && npm audit --audit-level=high` | Next.js and `eslint-config-next` were patched to the compatible secure line. Remaining audit findings are moderate only. | `frontend/package.json`; `frontend/package-lock.json`; `.github/workflows/ci.yml` | Lint, typecheck, test, build pass and no high/critical frontend audit findings remain. |
| 8 | Driver app has executable typecheck and honest risk tracking | Code-fixed; needs local Docker verification | `cd driver-app && npm run typecheck && npm run test:unit -- --runInBand && npm run test:rntl -- --runInBand --silent` | The repo now exposes a real `typecheck` script. Remaining Expo/Jest audit findings are documented in the risk register until the next SDK upgrade window. | `driver-app/package.json`; `driver-app/jest.config.js`; `docs/security/driver-app-dependency-risk-register.md`; `.github/workflows/ci.yml` | Typecheck and tests pass; unresolved audit items are documented with mitigation and owner. |
| 9 | Local Docker bootstrap, migration, seed, and smoke path are reproducible | Code-fixed; needs local Docker verification | `make local-reset && make local-bootstrap && make local-smoke` | Commands exist but require a Docker-capable operator environment; agent verification is manual/external. | `Makefile`; `infra/docker-compose.local.yml`; `scripts/seed_demo_data.py`; `scripts/verify_demo.py` | Local stack builds, migrates, seeds, and passes seeded-incident smoke checks. |
| 10 | AWS ECS/Fargate pilot deployment path is documented and scripted | Requires AWS/staging verification | `scripts/deploy/build_and_push_ecr.sh && scripts/deploy/run_migrations_ecs.sh && scripts/deploy/update_ecs_services.sh && scripts/deploy/smoke_staging.sh` | Kubernetes/GHCR manifests remain legacy/non-primary. ECS/Fargate is the documented pilot path. | `docs/operations/aws-ecs-pilot-deployment.md`; `infra/aws/ecs/`; `scripts/deploy/` | Staging deploy, migration, and smoke scripts succeed with real AWS credentials and secrets. |
| 11 | Backup/DR scripts referenced by docs actually exist | Requires AWS/staging verification | `scripts/backup/run_pg_full_backup.sh` and `scripts/backup/run_pg_wal_archive.sh` | Scripts are present and safe, but S3 uploads and restore timing still need a real environment drill. | `scripts/backup/`; `docs/operations/backup-dr/README.md`; `docs/operations/restore-drill.md`; `infra/production/postgres-backup-cronjob.yaml` | Backup scripts run with explicit env vars and a restore drill is completed with evidence. |
| 12 | Controlled-pilot onboarding, demo, support, and success docs exist | Verified complete | `test -f docs/pilot/pilot-onboarding-checklist.md && test -f docs/pilot/pilot-success-metrics.md && test -f docs/pilot/demo-script.md && test -f docs/support/operator-triage-runbook.md` | Pilot operator docs are now kept alongside operations docs. | `docs/pilot/`; `docs/support/` | Operators can onboard a pilot tenant, run the hero demo, measure pilot success, and triage common incidents. |
| 13 | Production SaaS hardening beyond the controlled pilot is explicitly deferred | Deferred beyond controlled pilot | `rg -n "Deferred beyond controlled pilot|Production SaaS" docs/operations/p0-pilot-readiness-checklist.md docs/operations/pilot-readiness-remediation-plan.md` | Broad SaaS concerns such as multi-region DR, full infra-as-code parity, advanced observability automation, and Expo major upgrades remain out of P0 scope. | `docs/operations/p0-pilot-readiness-checklist.md`; `docs/operations/pilot-readiness-remediation-plan.md` | Deferred items remain visible and do not block the controlled pilot. |

## Verification date

- Updated for this remediation pass: 2026-06-27

## Exact commands still expected before pilot sign-off

```bash
cd backend && APP_ENV=test pytest tests/ -q --durations=20
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build
cd frontend && npm audit --audit-level=high
cd driver-app && npm run typecheck
cd driver-app && npm run test:unit -- --runInBand
cd driver-app && npm run test:rntl -- --runInBand --silent
cd driver-app && npm audit --audit-level=high
make local-reset
make local-bootstrap
make local-smoke
scripts/deploy/build_and_push_ecr.sh
scripts/deploy/run_migrations_ecs.sh
scripts/deploy/update_ecs_services.sh
scripts/deploy/smoke_staging.sh
```
