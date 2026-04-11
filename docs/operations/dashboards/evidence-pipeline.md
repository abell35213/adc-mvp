# Evidence Pipeline Dashboard Spec

## Purpose
Provide end-to-end visibility into evidence ingest, processing, storage, and export reliability for compliance-sensitive workflows.

## Scope
- Environment: `prod`
- Service: `adc-evidence-pipeline`
- Org: `adc`
- Data sources: ingest API metrics, object-storage metrics, pipeline task metrics, export metrics

## Primary panels
1. **Evidence ingest success ratio**
   - Query: `sum(rate(evidence_ingest_requests_total{service="adc-evidence-pipeline",environment="prod",result="success"}[10m])) / sum(rate(evidence_ingest_requests_total{service="adc-evidence-pipeline",environment="prod"}[10m]))`
2. **Artifact processing latency p95**
   - Query: `histogram_quantile(0.95, sum by (le, stage) (rate(evidence_stage_duration_seconds_bucket{service="adc-evidence-pipeline",environment="prod"}[10m])))`
3. **Pipeline stage failure count by stage**
   - Query: `sum(rate(evidence_stage_failures_total{service="adc-evidence-pipeline",environment="prod"}[10m])) by (stage)`
4. **Storage write/read error rates**
   - Query: `sum(rate(evidence_storage_errors_total{service="adc-evidence-pipeline",environment="prod"}[5m])) by (operation)`
5. **Export package generation success ratio**
   - Query: `sum(rate(export_package_jobs_total{service="adc-evidence-pipeline",environment="prod",state="SUCCESS"}[15m])) / sum(rate(export_package_jobs_total{service="adc-evidence-pipeline",environment="prod"}[15m]))`
6. **Backlog of pending evidence artifacts**
   - Query: `max(evidence_pending_artifacts{service="adc-evidence-pipeline",environment="prod"})`

## Dashboard-level filters
- `org`: default `adc`
- `service`: default `adc-evidence-pipeline`
- `environment`: default `prod`
- `stage`: optional

## Linked alerts
- `evidence_ingest_failure_ratio_critical`
- `evidence_stage_latency_warning`
- `evidence_export_failures_critical`
- `integration_credentials_invalid_spike_warning`
- `integration_provider_outage_critical`
- `retry_scheduler_stuck_in_progress_critical`
- `dashcam_capture_failure_ratio_warning`
- `otp_delivery_failure_ratio_warning`
- `webhook_signature_failure_spike_warning`
- `retry_queue_backlog_warning`

## Reliability drill-down queries (new)
1. **Credential invalid spikes**
   - Query: `sum(increase(integration_provider_auth_failure_total{service="adc-worker",environment="prod"}[10m]))`
   - Threshold: warning at `> 5` in 10m; critical at `> 20` in 10m.
2. **Provider outage indicators**
   - Query: `sum(rate(integration_provider_failure_total{service="adc-worker",environment="prod"}[10m])) / clamp_min(sum(rate(integration_provider_requests_total{service="adc-worker",environment="prod"}[10m])), 1)`
   - Threshold: warning at `> 0.20` for 10m; critical at `> 0.40` for 10m.
3. **Stuck in-progress operations**
   - Query: `max(job_execution_stuck_total{service="adc-worker",environment="prod"})`
   - Threshold: warning at `> 10` for 15m; critical at `> 25` for 15m.
4. **Dashcam failure threshold breaches**
   - Query: `sum(rate(integration_operations_total{service="adc-worker",environment="prod",domain="dashcam",status=~"failed|unavailable"}[15m])) / clamp_min(sum(rate(integration_operations_total{service="adc-worker",environment="prod",domain="dashcam"}[15m])), 1)`
   - Threshold: warning at `> 0.15` for 15m; critical at `> 0.25` for 15m.
5. **OTP failure threshold breaches**
   - Query: `sum(rate(otp_delivery_failure_total{service="adc-api",environment="prod"}[10m])) / clamp_min(sum(rate(otp_delivery_attempts_total{service="adc-api",environment="prod"}[10m])), 1)`
   - Threshold: warning at `> 0.08` for 10m; critical at `> 0.15` for 10m.
6. **Webhook signature failure spikes**
   - Query: `sum(increase(webhook_signature_failures_total{service="adc-api",environment="prod"}[10m]))`
   - Threshold: warning at `> 10` in 10m; critical at `> 30` in 10m.
7. **Queue backlog thresholds**
   - Query: `max(celery_queue_depth{service="adc-worker",environment="prod"}) by (queue)`
   - Threshold: warning at `> 500` for 15m; critical at `> 1200` for 15m.

## Runbooks
- Primary: `docs/reliability-and-incident-response-runbook.md`
- Secondary: `docs/section-23-export-acceptance-checklist.md`
