# Celery task reliability: idempotency, retries, and dead letters

## Deterministic idempotency keys

The async incident workflows now generate stable idempotency keys so retries and duplicate deliveries are safe:

- `capture_dashcam`: key derived from `incident_id + window_start + window_end`.
- `capture_telematics_bundle`: key derived from `incident_id + window_start + window_end`.
- `build_export`: key derived from `incident_id + export_id`.
- `notify_safety_manager`: key derived from `incident_id`.

Each workflow writes `idempotency_key` in task-generated event payloads and uses it to guard duplicate event emission.

## Duplicate-processing guards

The task layer now uses idempotent guards to prevent duplicate side effects:

- Evidence tasks derive deterministic artifact UUIDs per stream/dataset/format and skip writes when artifact IDs already exist.
- Evidence tasks short-circuit as `skipped_duplicate` when the same workflow has already emitted a successful completion event.
- Export generation short-circuits if export row is already `ready` and a generated event exists for the same idempotency key.
- Notifications skip duplicate SMS/call sends when corresponding success events already exist for that incident workflow.

## Retry/backoff strategy

`backend/app/tasks/celery_app.py` configures task-level retry policy via Celery annotations:

- `autoretry_for=(Exception,)` on evidence/export/notification tasks.
- Exponential backoff enabled via `retry_backoff=True`.
- Capped backoff:
  - Evidence: max 300 seconds.
  - Export: max 180 seconds.
  - Notifications: max 120 seconds.
- Jitter enabled via `retry_jitter=True` to reduce thundering herds.

Global worker transport defaults also set:

- `task_default_retry_delay=30`
- `worker_prefetch_multiplier=1`
- `broker_transport_options.visibility_timeout=3600`

## Dead-letter strategy

When a task reaches terminal failure (retries exhausted), a `task_failure` signal handler routes metadata to a dedicated `dead_letter` queue using `record_dead_letter`.

Payload includes:

- task name and ID
- args/kwargs
- terminal exception text

Use this queue for operator triage, alerting, and replay tooling.

## Operations checklist

1. Monitor queue depths for `evidence`, `exports`, `notifications`, and `dead_letter`.
2. Alert on sustained growth in `dead_letter`.
3. Investigate dead-letter payloads and classify transient vs permanent failures.
4. Replay only after root-cause mitigation; idempotency controls prevent duplicate side effects for already-completed workflows.
