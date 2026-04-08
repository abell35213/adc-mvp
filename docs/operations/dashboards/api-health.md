# API Health Dashboard Spec

## Purpose
Track request-path reliability, latency, and saturation for customer-facing API endpoints required by the observability gate (Section 7.4).

## Scope
- Environment: `prod`
- Service: `adc-api`
- Org: `adc`
- Data sources: HTTP server metrics, ingress metrics, Postgres and Redis dependency health metrics

## Primary panels
1. **Request rate (RPS)**
   - Query: `sum(rate(http_server_requests_total{service="adc-api",environment="prod"}[5m]))`
2. **Error ratio (5xx / total)**
   - Query: `sum(rate(http_server_requests_total{service="adc-api",environment="prod",status=~"5.."}[5m])) / sum(rate(http_server_requests_total{service="adc-api",environment="prod"}[5m]))`
3. **p95 latency by route**
   - Query: `histogram_quantile(0.95, sum by (le, route) (rate(http_server_request_duration_seconds_bucket{service="adc-api",environment="prod"}[5m])))`
4. **Auth success vs failure ratio**
   - Query: `sum(rate(auth_attempts_total{service="adc-api",environment="prod",result="success"}[5m])) / sum(rate(auth_attempts_total{service="adc-api",environment="prod"}[5m]))`
5. **Dependency health rollup**
   - Queries: DB connection saturation, Redis timeout/error rate, OTP provider error rate
6. **SLO burn-rate panels (1h and 6h windows)**
   - Query pair for fast/slow burn on API error budget

## Dashboard-level filters
- `org`: default `adc`
- `service`: default `adc-api`
- `environment`: default `prod`
- `route`: optional wildcard

## Linked alerts
- `api_5xx_error_ratio_critical`
- `api_latency_p95_warning`
- `api_dependency_failure_critical`

## Runbooks
- Primary: `docs/reliability-and-incident-response-runbook.md`
- Secondary: `docs/release-readiness-checklist.md`
