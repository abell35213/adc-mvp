# P0 Pilot Readiness Checklist

Use this checklist for every controlled pilot demo release check. Keep statuses current and treat every P0 item as a launch blocker until its exit criteria are met.

Status values: `Done`, `In progress`, `Blocked`, `Needs local verification`.

## P0 launch blockers

| # | Checklist item | Status | Verification command | Independent verification notes | Link/path to relevant files | Exit criteria |
|---|---|---|---|---|---|---|
| 1 | Frontend dynamic deployment fixed | Blocked | `test ! -f .github/workflows/nextjs.yml && cd frontend && npm run build` | The CI workflow uses the dynamic Next.js build, but `.github/workflows/nextjs.yml` still deploys a static GitHub Pages artifact from `frontend/out`. Do not mark Done until that Pages workflow is removed or disabled and the production build path is the pilot deployment path. | `.github/workflows/ci.yml`; `.github/workflows/nextjs.yml`; `frontend/package.json`; `README.md`; `.env.example` | Production build completes and the obsolete GitHub Pages/static export deployment path is removed or disabled for pilot deployment. |
| 2 | Frontend typecheck/build/start passes | Done | `cd frontend && npm run typecheck && npm run build && timeout 10s npm run start` | Verified locally on 2026-06-18. `npm run build` completed with Next.js `cpus: 1`; `timeout 10s npm run start` reached `Ready` before timeout stopped the server. | `frontend/package.json`; `frontend/`; `frontend/tests/` | TypeScript check passes, Next.js production build passes, and production server starts successfully. |
| 3 | Local Docker Compose works without AWS secrets | Needs local verification | `cp .env.example .env && make local-bootstrap` | The Makefile and local compose stack are wired for local Postgres/Redis, `SECRET_PROVIDER=env`, filesystem storage, noop email, and blank live-provider credentials, but this Docker path is not Done until `make local-bootstrap` passes in the pilot operator's local environment. | `Makefile`; `infra/docker-compose.local.yml`; `.env.example`; `README.md` | Local stack builds, starts, migrates, seeds, and verifies using only local/default development secrets. |
| 4 | Local migration and seed flow works | Needs local verification | `make local-migrate && make local-seed && make local-verify-demo` | Commands exist and README documents the flow. Keep this separate from full bootstrap so migration/seed issues can be isolated after containers are healthy. | `Makefile`; `backend/alembic/`; `scripts/seed_demo_data.py`; `scripts/verify_demo.py` | Alembic reaches head, demo seed completes, and verification confirms the seeded tenant and login are usable. |
| 5 | Backend tests complete | Needs local verification | `make lint && make test` | CI documents backend lint, duplicate-module guard, targeted regressions, full pytest suite, schema validation, and runtime API contract checks. Do not mark Done until the repo-level backend gate passes locally for this cleanup. | `Makefile`; `.github/workflows/ci.yml`; `backend/pytest.ini`; `backend/tests/`; `scripts/validate_schemas.py` | Backend lint and full backend/schema test suite complete cleanly. |
| 6 | Driver app tests complete | Needs local verification | `cd driver-app && npm run test:serial` | Driver package provides serial Jest and coverage commands; CI uses `npm run test:coverage`. Do not mark Done until the documented local driver test command passes. | `driver-app/package.json`; `driver-app/TESTING.md`; `.github/workflows/ci.yml`; `driver-app/` | Driver app Jest suite completes without failures. |
| 7 | Local smoke test validates seeded incident workflow | Needs local verification | `make local-smoke` | Requires a running local API and worker from `make local-up` or `make local-bootstrap`; validates seeded demo data, login, incident access, export request, and export readiness. | `Makefile`; `scripts/verify_demo.py`; `backend/app/tasks/export_tasks.py` | Seeded demo login works, a seeded incident is accessible, export generation is requested, and export reaches ready status. |
| 8 | Org-level authorization tests pass | Needs local verification | `cd backend && APP_ENV=test pytest tests/test_authorization_regressions.py tests/test_api_endpoints.py::TestExportEndpoints::test_get_export_forbidden_for_other_org tests/test_export_section23_acceptance.py::test_authorization_and_org_isolation -q` | Keep this targeted command explicit for pilot sign-off. Expand it if new org-boundary tests are added. | `backend/tests/test_authorization_regressions.py`; `backend/tests/test_api_endpoints.py`; `backend/tests/test_export_section23_acceptance.py`; `backend/app/security/authz.py` | Cross-org incident/export/content access is rejected and authorization regression tests pass. |
| 9 | Demo login is documented | Done | `rg -n "demo-admin@adc.local|DemoAdmin!2345|DEMO_ADMIN_EMAIL|DEMO_ADMIN_PASSWORD" README.md .env.example scripts/seed_demo_data.py` | Verified by inspection on 2026-06-18: README documents the local demo email/password/org, `.env.example` provides matching frontend prefill values, and `scripts/seed_demo_data.py` uses the same default seeded credentials. | `README.md`; `.env.example`; `scripts/seed_demo_data.py` | Pilot operator can find the local demo URL, seeded email, seeded password, and organization name in repo docs. |
| 10 | Known non-P0 features are explicitly listed as out of pilot scope | Done | `rg -n "P1|P2|out of pilot scope|non-P0" docs/operations/p0-pilot-readiness-checklist.md` | P1/P2 work remains listed below and is explicitly separated from P0 launch blockers. | `docs/operations/p0-pilot-readiness-checklist.md` | Later work is visible and explicitly separated from P0 blockers. |

## Last verification commands

Commands run for the latest checklist update on 2026-06-18:

```bash
cd frontend && npm run typecheck && npm run build
timeout 10s npm run start
rg -n "demo-admin@adc.local|DemoAdmin!2345|DEMO_ADMIN_EMAIL|DEMO_ADMIN_PASSWORD" README.md .env.example scripts/seed_demo_data.py
rg -n "P1|P2|out of pilot scope|non-P0" docs/operations/p0-pilot-readiness-checklist.md
```

Known remaining P0 verification commands before P1:

```bash
# Remove or disable .github/workflows/nextjs.yml first, then verify the pilot frontend build path.
test ! -f .github/workflows/nextjs.yml && cd frontend && npm run build

# Verify the local-only Docker bootstrap and seeded demo smoke path.
cp .env.example .env
make local-bootstrap
make local-smoke

# If debugging bootstrap in smaller steps, verify migration/seed separately.
make local-migrate && make local-seed && make local-verify-demo

# Verify backend and schema gates.
make lint && make test
cd backend && APP_ENV=test pytest tests/test_authorization_regressions.py tests/test_api_endpoints.py::TestExportEndpoints::test_get_export_forbidden_for_other_org tests/test_export_section23_acceptance.py::test_authorization_and_org_isolation -q

# Verify driver app tests.
cd driver-app && npm run test:serial
```

## Remaining P0 blockers

- `.github/workflows/nextjs.yml` still defines a GitHub Pages static deployment path and must be removed or disabled before the frontend dynamic deployment item can be marked `Done`.
- Docker-based local bootstrap/smoke items remain `Needs local verification` until `make local-bootstrap` and `make local-smoke` pass.
- Backend, driver app, and org-authorization test items remain `Needs local verification` until their documented commands pass locally for the P0 release candidate.

## Out of pilot scope: known P1/P2 work

These items are not P0 blockers for the controlled pilot demo unless they are explicitly promoted into the table above.

- **P1:** Production-grade cloud secret rotation and live provider credential rollout beyond the local-only pilot stack.
- **P1:** Full staging/production Kubernetes deployment hardening beyond validating the pilot deployment mode.
- **P1:** Expanded analytics, reporting dashboards, and commercial growth workflows not needed for the seeded demo path.
- **P2:** Additional third-party integrations beyond the mocked/seeded incident-to-export pilot workflow.
- **P2:** Broad UX polish, advanced onboarding automation, and non-critical mobile enhancements outside driver app test stability.

## Release check notes

- Change a row to `In progress` only when an owner is actively working it.
- Change a row to `Blocked` when a known repo or environment issue prevents truthful completion.
- Change a row to `Needs local verification` when the repo appears wired for the item but the required command has not passed for this release candidate.
- Change a row to `Done` only after the verification command has passed and the exit criteria are true.
- If a verification command is intentionally replaced, update this file in the same PR so the next release check remains repeatable.
