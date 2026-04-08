# Security & Audit Dashboard Spec

## Purpose
Track security posture and audit pipeline health, including immutable event generation and ingestion timeliness.

## Scope
- Environment: `prod`
- Service: `adc-security-audit`
- Org: `adc`
- Data sources: auth/audit logs, SIEM ingestion metrics, admin action audit events

## Primary panels
1. **Authentication failure ratio by reason**
   - Query: `sum(rate(auth_failures_total{service="adc-security-audit",environment="prod"}[10m])) by (reason) / sum(rate(auth_attempts_total{service="adc-security-audit",environment="prod"}[10m]))`
2. **Privileged action count by actor role**
   - Query: `sum(rate(admin_privileged_actions_total{service="adc-security-audit",environment="prod"}[15m])) by (actor_role, action)`
3. **Audit event ingestion lag (p95)**
   - Query: `histogram_quantile(0.95, sum by (le) (rate(audit_ingestion_lag_seconds_bucket{service="adc-security-audit",environment="prod"}[10m])))`
4. **Audit event drop/parse failures**
   - Query: `sum(rate(audit_event_failures_total{service="adc-security-audit",environment="prod"}[10m])) by (failure_type)`
5. **Cross-tenant access-denied attempts**
   - Query: `sum(rate(authz_cross_tenant_denied_total{service="adc-security-audit",environment="prod"}[10m]))`
6. **Tamper-evidence validator status**
   - Query: `max(audit_tamper_validation_pass{service="adc-security-audit",environment="prod"})`

## Dashboard-level filters
- `org`: default `adc`
- `service`: default `adc-security-audit`
- `environment`: default `prod`
- `actor_role`: optional

## Linked alerts
- `security_auth_failure_ratio_warning`
- `audit_ingestion_lag_critical`
- `audit_pipeline_failure_critical`

## Runbooks
- Primary: `docs/reliability-and-incident-response-runbook.md`
- Secondary: `docs/release-readiness-checklist.md`
