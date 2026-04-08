# Reliability Targets, Recovery Drills, and Incident Runbooks

## Purpose

This document defines:

- Recovery Point Objective (RPO) and Recovery Time Objective (RTO) targets.
- Backup and restore procedures for PostgreSQL, Redis, and artifact storage.
- Periodic disaster-recovery (DR) drill procedures and owner assignments.
- Escalation paths and response runbooks for common outage/data-risk scenarios.

Use this runbook alongside credential/key rotation runbooks in `docs/`.

Use detailed backup/DR artifacts in `docs/operations/backup-dr/` for operational execution checklists and playbooks.


## 1) Service ownership and on-call assignments

| Area | Primary owner | Secondary owner | Escalation manager |
| --- | --- | --- | --- |
| PostgreSQL data plane | Backend on-call engineer | Platform on-call engineer | Engineering manager |
| Redis cache/queue state | Platform on-call engineer | Backend on-call engineer | Engineering manager |
| Artifact storage (S3/object store) | Platform on-call engineer | Backend on-call engineer | Engineering manager |
| Authentication services (JWT/OTP/session) | Backend on-call engineer | Security engineer | Engineering manager |
| Twilio integrations | Backend on-call engineer | Support engineer | Engineering manager |
| Export pipeline | Data/platform on-call engineer | Backend on-call engineer | Engineering manager |
| Data integrity incidents | Incident commander (IC) from on-call rotation | Security/compliance representative | CTO or delegate |

### Incident command roles (for Sev-1 and Sev-2)

- **Incident Commander (IC):** leads response timeline and decisions.
- **Comms Lead:** posts internal updates every 15 minutes (Sev-1) or 30 minutes (Sev-2).
- **Ops Lead:** executes infrastructure and rollout/rollback actions.
- **Scribe:** captures timestamps, decisions, and customer impact.

## 2) Reliability targets (RPO / RTO)

| System | RPO target | RTO target | Notes |
| --- | --- | --- | --- |
| PostgreSQL (primary transactional store) | <= 15 minutes | <= 60 minutes | PITR-capable backups required. |
| Redis (cache + transient queue state) | <= 60 minutes | <= 30 minutes | Some cache loss acceptable; queue replay required. |
| Artifact storage (evidence/export objects) | <= 15 minutes | <= 120 minutes | Versioning + cross-region copy recommended. |

### Target interpretation

- **RPO** = maximum tolerated data loss window.
- **RTO** = maximum tolerated time to restore service.
- If an incident is projected to exceed RTO, immediately escalate to Engineering Manager and declare customer-impact status page update.

## 3) Backup policy and restore steps

## 3.1 PostgreSQL backup and restore

### Backup policy

- Full snapshot: daily at 02:00 UTC.
- Incremental/WAL archival: continuous (or at most every 5 minutes).
- Retention:
  - Daily backups: 35 days.
  - Weekly backups: 12 weeks.
  - Monthly backups: 12 months.
- Backups encrypted at rest and in transit.
- Backup success alarms routed to on-call channel.

### Restore procedure (PITR)

1. Declare incident and freeze destructive write operations if possible.
2. Identify target recovery timestamp (last known-good point).
3. Provision restore instance from latest full snapshot.
4. Apply WAL/incremental logs up to recovery timestamp.
5. Run schema/version checks and critical query smoke tests.
6. Promote restore instance to primary.
7. Repoint `DATABASE_URL` secret and restart backend + workers.
8. Validate API write/read paths and background jobs.
9. Keep previous primary isolated for forensics until incident closure.

### PostgreSQL restore validation checklist

- Can create/read/update an incident record.
- Can attach and query artifact metadata records.
- Background worker tasks involving DB complete successfully.
- No migration drift (`alembic current` matches expected head).

## 3.2 Redis backup and restore

### Backup policy

- Enable AOF (append-only) with `everysec` or equivalent durability.
- Snapshot (RDB) every 15 minutes.
- Retain snapshots for 7 days minimum.
- Monitor memory pressure and replication lag alarms.

### Restore procedure

1. Triage: determine whether Redis is used as cache-only or includes queue/stateful workloads.
2. If cache-only: recreate cluster and allow warmup from DB (fast-path recovery).
3. If queue/stateful: restore from latest snapshot + AOF replay.
4. Reconnect workers and verify queue consumers are healthy.
5. Replay missed jobs from durable source (DB outbox or task table) when available.
6. Flush only corrupted keyspaces (avoid global flush unless approved by IC).

### Redis restore validation checklist

- Worker heartbeat and queue depth normalize.
- No sustained `connection refused` or timeout errors from backend/worker.
- OTP/session/cache lookups recover within expected latency.

## 3.3 Artifact storage backup and restore

### Backup policy

- Object versioning enabled on all production buckets.
- Cross-region replication or scheduled copy every 15 minutes.
- Lifecycle policy:
  - Current versions retained per product retention requirements.
  - Non-current versions retained at least 90 days.
- Daily inventory/report of object replication status.

### Restore procedure

1. Identify scope (single object, prefix, full bucket, region outage).
2. For accidental delete/overwrite: restore prior object version.
3. For bucket-level corruption: restore from replicated region or backup copy job.
4. Rebuild any derived artifacts (thumbnails, preview PDFs, export bundles).
5. Validate object ACL/presigned URL behavior and integrity hashes.

### Artifact restore validation checklist

- Target objects downloadable by authorized users.
- Hash/checksum matches expected metadata for sampled files.
- Export package generation includes restored artifacts.

## 4) Periodic recovery drill program

## Frequency and scope

- **Monthly:** tabletop drill (90 minutes) covering one outage scenario.
- **Quarterly:** hands-on technical recovery drill per data system:
  - Q1: PostgreSQL PITR drill.
  - Q2: Redis queue/state recovery drill.
  - Q3: Artifact storage regional failover drill.
  - Q4: Full cross-system game day.

## Drill owners

- DR program owner: Platform lead.
- Scenario owner: service primary owner from the ownership matrix.
- Audit/compliance observer: Security/compliance representative.

## Drill execution checklist

1. Define scenario, success criteria, and simulated impact window.
2. Capture baseline metrics (error rate, queue lag, DB replication position).
3. Execute recovery steps exactly from this runbook.
4. Measure achieved RTO/RPO vs targets.
5. Record deviations, manual steps, missing tooling, and communication gaps.
6. File corrective actions with owner + due date (<= 30 days for Sev-1 gaps).
7. Publish drill report in `docs/` history or incident knowledge base.

## Minimum evidence to retain per drill

- Date/time, participants, and assigned IC.
- Start of outage simulation and service restore timestamp.
- Estimated data loss window (actual RPO).
- Screenshots/log extracts proving service restoration.
- Follow-up tickets and completion status.

## 5) Escalation policy and communication paths

## Severity levels

- **Sev-1:** broad customer impact, security/integrity risk, or projected RTO breach.
- **Sev-2:** partial degradation with workaround; limited customer impact.
- **Sev-3:** localized issue, no active customer impact.

## Escalation path

1. On-call engineer acknowledges page within 5 minutes.
2. If unresolved in 15 minutes or Sev-1 suspected, page secondary owner and Engineering Manager.
3. For suspected security/data integrity issues, add Security/Compliance immediately.
4. If customer-facing impact > 30 minutes, Comms Lead posts status update and support macro.
5. If legal/regulatory exposure exists, notify executive escalation (CTO + legal/compliance lead).

## Communication channels

- Primary: `#incidents` (chat) + incident video bridge.
- Paging: on-call provider schedules/escalations.
- External: status page + support broadcast templates.

## 6) Scenario runbooks

## 6.1 Authentication outage runbook

### Triggers

- Login/signup failure spikes.
- JWT verification failures.
- OTP request/verify failures not isolated to Twilio provider.

### Immediate actions

1. Declare incident and assign IC.
2. Check backend error logs for auth code paths.
3. Validate secrets availability (`JWT_*`, OTP/Twilio settings).
4. Verify DB connectivity for auth tables (users/sessions/OTP).
5. If recent deploy touched auth paths, initiate rollback/canary disable.
6. If OTP dependency issue is Twilio-specific, transition to Twilio outage runbook.

### Mitigation options

- Temporarily extend existing session TTL for already authenticated users.
- Rate-limit auth endpoints to protect dependencies.
- Switch to backup OTP provider if supported.

### Exit criteria

- Login and token refresh success rates back to baseline.
- Error budget burn normalized for 30 minutes.
- Customer support volume returns to normal trend.

## 6.2 Twilio outage runbook

### Triggers

- Twilio API errors/timeouts spike.
- OTP SMS/voice delivery failure rate above alert threshold.

### Immediate actions

1. Confirm Twilio service status and internal failure metrics.
2. Declare dependency incident and set user-facing messaging.
3. Pause aggressive retry storms; enable bounded retries with jitter.
4. Prioritize critical flows (account recovery, admin access).

### Mitigation options

- Fail over to secondary OTP/notification provider (if configured).
- Fallback to backup channel (voice over SMS or email link) where policy allows.
- Temporarily disable non-critical notifications.

### Exit criteria

- Successful OTP delivery/verification above baseline threshold.
- Backlog of retries drained.
- Support macros retired and post-incident summary published.

## 6.3 Export pipeline failure runbook

### Triggers

- Export jobs stuck/failed beyond SLA.
- Queue lag or worker crash loop impacting export tasks.

### Immediate actions

1. Confirm failure domain: API enqueue, worker execution, storage upload, or notification step.
2. Check worker health, queue depth, and recent deploys.
3. Pause new low-priority exports if queue saturation is severe.
4. Requeue idempotent failed jobs after root-cause triage.

### Mitigation options

- Scale worker concurrency temporarily.
- Route large exports to dedicated queue.
- Provide manual export generation for top-priority customers.

### Exit criteria

- Queue depth and processing latency back within SLO.
- Error rate for export tasks stabilized for 60 minutes.
- All priority failed exports reprocessed or customer-communicated.

## 6.4 Data integrity incident runbook

### Triggers

- Missing/corrupted records or mismatched counts.
- Integrity constraint violations or checksum mismatches.
- Suspected unauthorized mutation/deletion.

### Immediate actions

1. Declare Sev-1 and appoint IC + Security/Compliance representative.
2. Stop or gate writes in affected domain (feature flag/read-only mode).
3. Preserve evidence: snapshots, audit logs, and relevant application logs.
4. Scope blast radius (tables/entities/time window/customers).
5. Decide restore strategy: point repair vs PITR vs object version restore.

### Remediation flow

1. Restore to isolated environment first; validate repair script.
2. Run reconciliation queries/checksums.
3. Obtain IC + data owner approval before production replay.
4. Execute production repair with rollback checkpoint.
5. Monitor for recurrence and validate downstream exports/reports.

### Exit criteria

- Integrity checks pass for affected datasets.
- Customer-visible discrepancies resolved or communicated.
- Incident report includes root cause, timeline, and prevention actions.

## 7) Post-incident requirements

- Publish incident review within 5 business days for Sev-1/Sev-2.
- Include: root cause, detection gaps, response timeline, customer impact, and corrective actions.
- Track corrective actions to closure with named owner and target date.
- Update this runbook when procedures or systems change.
