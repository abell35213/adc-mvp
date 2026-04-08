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

## Runbooks
- Primary: `docs/reliability-and-incident-response-runbook.md`
- Secondary: `docs/section-23-export-acceptance-checklist.md`
