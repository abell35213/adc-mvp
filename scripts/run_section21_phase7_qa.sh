#!/usr/bin/env bash
set -euo pipefail

SCENARIO="${1:-all}"

cat <<'USAGE' >&2
Section 21 (Phase 7) QA runbook helper.

Usage:
  bash scripts/run_section21_phase7_qa.sh <scenario>

Scenarios:
  endpoint_authn_authz
  entitlement_enforcement
  demo_reset_reseed_idempotency
  deployment_progress_readiness
  docs_trust_visibility
  frontend_feature_gates
  all
USAGE

print_step() {
  local scenario_name="$1"
  shift
  if [[ "$SCENARIO" == "all" || "$SCENARIO" == "$scenario_name" ]]; then
    echo
    echo "=== ${scenario_name} ==="
    "$@"
  fi
}

endpoint_authn_authz() {
  cat <<'EOF_STEP'
1) Call /org/entitlements, /demo/scenarios, /org/deployment-progress, /trust/sections without auth.
2) Confirm all responses are HTTP 401.
3) Call /trust/internal/sections as org_admin and confirm HTTP 403.
4) Patch /org/deployment-scope as read_only role and confirm HTTP 403.
Reference test: backend/tests/test_section21_phase7_routes.py::test_section21_endpoint_authn_and_authz
EOF_STEP
}

entitlement_enforcement() {
  cat <<'EOF_STEP'
1) Set org entitlements for demo.workspace, demo.incident_seed, trust.audit_controls to false.
2) Call /demo/scenarios and /trust/sections as authenticated org_admin.
3) Confirm both responses are HTTP 404 (feature unavailable / hidden surface).
Reference test: backend/tests/test_section21_phase7_routes.py::test_section21_entitlement_enforcement_hides_disabled_surfaces
EOF_STEP
}

demo_reset_reseed_idempotency() {
  cat <<'EOF_STEP'
1) Seed demo with scenario driver_minor_collision.
2) Reset demo and capture deleted counters.
3) Seed again with same scenario and reset again.
4) Confirm both reset calls return 200 and identical deleted-key shape.
Reference test: backend/tests/test_section21_phase7_routes.py::test_section21_demo_reset_reseed_is_idempotent
EOF_STEP
}

deployment_progress_readiness() {
  cat <<'EOF_STEP'
1) Query /org/deployment-progress as org_admin.
2) Validate scope and percent_complete shape + coverage collection.
3) Query /org/expansion-readiness and validate status is one of allowed readiness states.
Reference test: backend/tests/test_section21_phase7_routes.py::test_section21_deployment_progress_and_readiness_states
EOF_STEP
}

docs_trust_visibility() {
  cat <<'EOF_STEP'
1) Seed one published trust section and one draft trust section.
2) Query /trust/sections with publication_state=published + audience filter.
3) Confirm draft section is excluded.
4) Query /trust/sections with publication_state=all and confirm draft section appears.
Reference test: backend/tests/test_section21_phase7_routes.py::test_section21_trust_publication_visibility_filters
EOF_STEP
}

frontend_feature_gates() {
  cat <<'EOF_STEP'
1) Validate feature-gating source supports lock/hide states and disabled UI semantics.
2) Validate deployment page includes readiness banner + coverage cards.
3) Validate trust page includes trust-center render states for core sections.
Reference tests:
- frontend/tests/featureGating.test.mjs
- frontend/tests/keyPageRenderStates.test.mjs
EOF_STEP
}

print_step "endpoint_authn_authz" endpoint_authn_authz
print_step "entitlement_enforcement" entitlement_enforcement
print_step "demo_reset_reseed_idempotency" demo_reset_reseed_idempotency
print_step "deployment_progress_readiness" deployment_progress_readiness
print_step "docs_trust_visibility" docs_trust_visibility
print_step "frontend_feature_gates" frontend_feature_gates
