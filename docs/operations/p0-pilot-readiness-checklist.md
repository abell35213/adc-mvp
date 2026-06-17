# P0 Pilot Readiness Checklist

Use this checklist for every controlled pilot demo release check. Keep statuses current and treat every P0 item as a launch blocker until its exit criteria are met.

Status values: `Not started`, `In progress`, `Done`.

## P0 launch blockers

| # | Checklist item | Status | Verification command | Owner notes | Link/path to relevant files | Exit criteria |
|---|---|---|---|---|---|---|
| 1 | Frontend dynamic deployment fixed | Not started | `cd frontend && npm run build` | Confirm the production build does not depend on demo-only prefills or local-only runtime assumptions. | `frontend/package.json`; `README.md`; `.env.example` | Production build completes and deployment/runtime mode is documented for the pilot environment. |
| 2 | Frontend typecheck/build/start passes | Not started | `cd frontend && npm run typecheck && npm run build && npm run start` | Run `npm run start` only after a successful build; stop the server after confirming it boots. | `frontend/package.json`; `frontend/`; `frontend/tests/` | TypeScript check passes, Next.js production build passes, and production server starts successfully. |
| 3 | Local Docker Compose works without AWS secrets | Not started | `cp .env.example .env && make local-bootstrap` | Use the local-only compose stack, not the staging-oriented compose file. It must not require AWS Secrets Manager or live provider credentials. | `Makefile`; `infra/docker-compose.local.yml`; `.env.example`; `README.md` | Local stack builds, starts, migrates, seeds, and verifies using only local/default development secrets. |
| 4 | Local migration and seed flow works | Not started | `make local-migrate && make local-seed && make local-verify-demo` | Seed flow must be idempotent and keep the documented demo admin usable. | `Makefile`; `backend/app/db/migrations/`; `scripts/seed_demo_data.py`; `scripts/verify_demo.py` | Alembic reaches head, demo seed completes, and verification confirms the seeded tenant and login are usable. |
| 5 | Backend tests complete | Not started | `make lint && make test` | Backend lint/type/test gate for release readiness; investigate any skipped or flaky tests before pilot sign-off. | `Makefile`; `backend/pytest.ini`; `backend/tests/`; `scripts/validate_schemas.py` | Backend lint and full backend/schema test suite complete cleanly. |
| 6 | Driver app tests complete | Not started | `cd driver-app && npm test -- --runInBand` | Use serial mode if open handles or Expo/Jest timing make failures hard to read. | `driver-app/package.json`; `driver-app/TESTING.md`; `driver-app/` | Driver app Jest suite completes without failures. |
| 7 | Local smoke test validates seeded incident workflow | Not started | `make local-smoke` | Requires the local API and worker from `make local-up`/`make local-bootstrap`; validates seeded incident-to-export flow. | `Makefile`; `scripts/verify_demo.py`; `backend/app/tasks/export_tasks.py` | Seeded demo login works, a seeded incident is accessible, export generation is requested, and export reaches ready status. |
| 8 | Org-level authorization tests pass | Not started | `cd backend && APP_ENV=test pytest tests/test_authorization_regressions.py tests/test_api_endpoints.py::TestExportEndpoints::test_get_export_forbidden_for_other_org tests/test_export_section23_acceptance.py::test_authorization_and_org_isolation -q` | Keep cross-org access checks explicit for pilot sign-off. Expand this command if new org-boundary tests are added. | `backend/tests/test_authorization_regressions.py`; `backend/tests/test_api_endpoints.py`; `backend/tests/test_export_section23_acceptance.py`; `backend/app/security/authz.py` | Cross-org incident/export/content access is rejected and authorization regression tests pass. |
| 9 | Demo login is documented | Not started | `rg -n "demo-admin@adc.local|DemoAdmin!2345|DEMO_ADMIN_EMAIL|DEMO_ADMIN_PASSWORD" README.md .env.example scripts/seed_demo_data.py` | Confirm docs match seed defaults before each pilot; never document production credentials here. | `README.md`; `.env.example`; `scripts/seed_demo_data.py` | Pilot operator can find the local demo URL, seeded email, seeded password, and organization name in repo docs. |
| 10 | Known non-P0 features are explicitly listed as out of pilot scope | Not started | `rg -n "P1|P2|out of pilot scope|non-P0" docs/operations/p0-pilot-readiness-checklist.md` | Update the P1/P2 list below when triage changes; do not block the pilot on these unless promoted to P0. | `docs/operations/p0-pilot-readiness-checklist.md` | Later work is visible and explicitly separated from P0 blockers. |

## Out of pilot scope: known P1/P2 work

These items are not P0 blockers for the controlled pilot demo unless they are explicitly promoted into the table above.

- **P1:** Production-grade cloud secret rotation and live provider credential rollout beyond the local-only pilot stack.
- **P1:** Full staging/production Kubernetes deployment hardening beyond validating the pilot deployment mode.
- **P1:** Expanded analytics, reporting dashboards, and commercial growth workflows not needed for the seeded demo path.
- **P2:** Additional third-party integrations beyond the mocked/seeded incident-to-export pilot workflow.
- **P2:** Broad UX polish, advanced onboarding automation, and non-critical mobile enhancements outside driver app test stability.

## Release check notes

- Change a row to `In progress` only when an owner is actively working it.
- Change a row to `Done` only after the verification command has passed and the exit criteria are true.
- If a verification command is intentionally replaced, update this file in the same PR so the next release check remains repeatable.
