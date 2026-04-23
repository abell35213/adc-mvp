# Section 21 MVP Acceptance Checklist

This checklist maps Section 21 MVP criteria to executable tests and repeatable QA evidence.

## MVP criteria (Section 21 MVP)

- [ ] **MVP-21.1 Endpoint authentication coverage**
  - Verify unauthenticated access to Section 21 routes returns `401`.
  - Automated evidence: `backend/tests/test_section21_phase7_routes.py::test_section21_endpoint_authn_and_authz`.

- [ ] **MVP-21.2 Endpoint authorization boundaries**
  - Verify privileged routes reject insufficient roles (`403`).
  - Automated evidence: `backend/tests/test_section21_phase7_routes.py::test_section21_endpoint_authn_and_authz`.

- [ ] **MVP-21.3 Entitlement enforcement / hidden capability behavior**
  - Verify disabled entitlements return non-disclosing feature-unavailable responses.
  - Automated evidence: `backend/tests/test_section21_phase7_routes.py::test_section21_entitlement_enforcement_hides_disabled_surfaces`.

- [ ] **MVP-21.4 Demo reset/reseed idempotency**
  - Repeated `seed -> reset -> seed -> reset` flows succeed with stable response shape.
  - Automated evidence: `backend/tests/test_section21_phase7_routes.py::test_section21_demo_reset_reseed_is_idempotent`.

- [ ] **MVP-21.5 Deployment progress/readiness state contracts**
  - Verify response shape and readiness status enum behavior remain stable.
  - Automated evidence: `backend/tests/test_section21_phase7_routes.py::test_section21_deployment_progress_and_readiness_states`.

- [ ] **MVP-21.6 Docs/trust publication visibility**
  - Verify published-only views hide drafts while `publication_state=all` includes them.
  - Automated evidence: `backend/tests/test_section21_phase7_routes.py::test_section21_trust_publication_visibility_filters`.

- [ ] **MVP-21.7 Frontend feature gates and key page render states**
  - Verify lock/hide feature-gate semantics and deployment/trust page baseline render states.
  - Automated evidence:
    - `frontend/tests/featureGating.test.mjs`
    - `frontend/tests/keyPageRenderStates.test.mjs`

## Repeatable QA execution

- Run scripted acceptance helper: `bash scripts/run_section21_phase7_qa.sh all`.
- Run backend verification: `cd backend && pytest tests/test_section21_phase7_routes.py -v`.
- Run frontend verification: `cd frontend && npm test`.
