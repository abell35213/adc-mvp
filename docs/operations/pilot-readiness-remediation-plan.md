# Pilot Readiness Remediation Plan

## What was found

- Backend, frontend, driver app, local Docker, and CI entry points already exist and are close to pilot-ready.
- `docs/operations/p0-pilot-readiness-checklist.md` was stale: it referenced a removed GitHub Pages workflow and an outdated pytest node id.
- Backend test reliability risk centered on Redis-backed rate limiting in `APP_ENV=test`; the repo already had a fake Redis helper but not a suite-wide default override.
- Production-safety validation existed for secrets/cookies, but `PDF_RENDER_FAIL_OPEN` still needed an explicit prod-like environment guard.
- The frontend was pinned to `next@16.2.4`; `npm audit` reported a high-severity Next.js advisory that is fixed by a compatible patch release.
- The driver app lacked a `typecheck` script and still carries Expo/Jest transitive audit findings that are not all safely fixable inside the current Expo major line.
- The existing deploy automation and manifests are Kubernetes/GHCR oriented; the controlled-pilot target architecture is AWS ECR + ECS/Fargate.
- Backup/DR docs referenced executable backup scripts that were missing from `scripts/backup/`.

## What is fixed in this PR

- Added this remediation plan and refreshed the P0 pilot readiness checklist with accurate statuses and commands.
- Added deterministic backend test defaults so rate-limit paths use fake Redis during `APP_ENV=test` instead of attempting real network resolution.
- Added a prod/staging guard so `PDF_RENDER_FAIL_OPEN=true` is rejected outside `local`/`test`.
- Redacted raw driver-initiated idempotency keys from workflow event payloads and kept hashed metadata only.
- Upgraded frontend Next.js / eslint-config-next to the patched compatible line and refreshed the lockfile.
- Added a real driver app `typecheck` script and captured remaining driver dependency exposure in a risk register.
- Added AWS ECS/Fargate pilot deployment documentation, ECS task-definition templates, deploy scripts, backup scripts, and restore-drill guidance.
- Added pilot onboarding, success-metrics, demo, and operator-triage runbooks.
- Updated CI so frontend checks include the higher audit threshold and driver validation includes typecheck plus a documented non-blocking audit step.

## Manual or external follow-up still required

- Run `make local-reset && make local-bootstrap && make local-smoke` on a Docker-capable workstation.
- Run the full backend suite locally if the agent environment cannot complete it reliably enough for timing-sensitive confidence.
- Provision AWS resources and secrets: ECR repos, ECS cluster/services, task execution roles, Secrets Manager secret ARNs, RDS, Redis/Valkey, S3 buckets, CloudWatch log groups, and ALB DNS/TLS.
- Validate ECS deployment and smoke-test scripts with real AWS credentials.
- Re-run the driver app audit after the next Expo SDK upgrade window; remaining findings are tracked in `docs/security/driver-app-dependency-risk-register.md`.
- Perform a non-production restore drill using `docs/operations/restore-drill.md` and record timestamps/evidence.

## Exact verification commands

### Backend

```bash
cd backend && APP_ENV=test pytest tests/test_driver_admin_endpoints.py -q --durations=20
cd backend && APP_ENV=test pytest tests/test_api_endpoints.py::TestGetExport::test_get_export_forbidden_for_other_org -q
cd backend && APP_ENV=test pytest tests/ -q --durations=20
```

### Frontend

```bash
cd frontend && npm install
cd frontend && npm audit --audit-level=high
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run test
cd frontend && npm run build
```

### Driver app

```bash
cd driver-app && npm install
cd driver-app && npm audit --audit-level=high
cd driver-app && npm run typecheck
cd driver-app && npm run test:unit -- --runInBand
cd driver-app && npm run test:rntl -- --runInBand --silent
```

### Local Docker

```bash
make local-reset
make local-bootstrap
make local-smoke
```

### AWS / staging manual verification

```bash
scripts/deploy/build_and_push_ecr.sh
scripts/deploy/run_migrations_ecs.sh
scripts/deploy/update_ecs_services.sh
scripts/deploy/smoke_staging.sh
```
