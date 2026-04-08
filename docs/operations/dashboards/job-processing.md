# Job Processing Dashboard Spec

## Purpose
Monitor asynchronous worker throughput, failures, retry patterns, and queue health to maintain Section 7.4 observability requirements and Section 21 post-release verification readiness.

## Scope
- Environment: `prod`
- Service: `adc-worker`
- Org: `adc`
- Data sources: Celery/queue metrics, worker runtime metrics, Redis queue metrics

## Primary panels
1. **Jobs started/completed rate**
   - Query: `sum(rate(celery_tasks_total{service="adc-worker",environment="prod",state=~"STARTED|SUCCESS"}[5m])) by (state)`
2. **Job failure ratio**
   - Query: `sum(rate(celery_tasks_total{service="adc-worker",environment="prod",state="FAILURE"}[15m])) / sum(rate(celery_tasks_total{service="adc-worker",environment="prod"}[15m]))`
3. **Queue depth by queue name**
   - Query: `max(celery_queue_depth{service="adc-worker",environment="prod"}) by (queue)`
4. **Oldest message age**
   - Query: `max(celery_queue_oldest_message_age_seconds{service="adc-worker",environment="prod"}) by (queue)`
5. **Retry storm detection**
   - Query: `sum(rate(celery_task_retries_total{service="adc-worker",environment="prod"}[10m])) by (task_name)`
6. **Worker availability**
   - Query: `sum(up{service="adc-worker",environment="prod"})`

## Dashboard-level filters
- `org`: default `adc`
- `service`: default `adc-worker`
- `environment`: default `prod`
- `queue`: optional

## Linked alerts
- `jobs_failure_ratio_critical`
- `jobs_queue_depth_warning`
- `jobs_stuck_message_critical`

## Runbooks
- Primary: `docs/reliability-and-incident-response-runbook.md`
- Secondary: `docs/section-23-export-acceptance-checklist.md`
