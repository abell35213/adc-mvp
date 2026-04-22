# Section 21 Production-Ready Acceptance Checklist

This checklist extends Section 21 MVP validation with release-grade operational proof for production onboarding.

## Production-ready criteria (Section 21 PR)

- [ ] **PR-21.1 Gate MVP criteria before promotion**
  - All entries in `docs/section-21-mvp-acceptance-checklist.md` are complete.

- [ ] **PR-21.2 Deterministic QA runbook execution**
  - Execute `bash scripts/run_section21_phase7_qa.sh all` in staging.
  - Record pass/fail plus timestamped operator notes.

- [ ] **PR-21.3 Backend regression lock for Section 21 routes**
  - Execute `cd backend && pytest tests/test_section21_phase7_routes.py -v`.
  - Archive test output artifact in release evidence package.

- [ ] **PR-21.4 Frontend regression lock for gating + page states**
  - Execute `cd frontend && npm run lint && npm test`.
  - Capture and archive output for release checklist traceability.

- [ ] **PR-21.5 Routing integrity checks in app bootstrap**
  - Confirm required Section 21 routers are registered in `backend/app/main.py`.
  - Validate `/webhooks/twilio/*` callbacks and Section 21 route prefixes resolve in deployed environment.

- [ ] **PR-21.6 Release decision evidence package**
  - Include:
    1. backend test run output,
    2. frontend lint + test output,
    3. QA script execution notes,
    4. checklist completion sign-off.

## Sign-off template

- Environment:
- Build/version:
- Date:
- Operator:
- Reviewer:
- Decision: `GO` / `NO-GO`
- Notes / blockers:
