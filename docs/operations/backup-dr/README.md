# Backup & Disaster Recovery (DR) Operations

## Scope

This package defines production backup automation requirements, disaster recovery objectives, and operator playbooks for:

- PostgreSQL backup and point-in-time restore.
- Object storage versioning/lifecycle controls.
- Secrets/configuration recovery.
- DNS/ingress recovery.
- Third-party/key dependency outage response.

Use this directory with `infra/production/postgres-backup-cronjob.yaml`, `infra/production/object-storage-policies.yaml`, `scripts/backup/run_pg_full_backup.sh`, and `scripts/backup/run_pg_wal_archive.sh`.

## Explicit service targets (RPO/RTO)

| System | RPO target | RTO target | Owner |
| --- | --- | --- | --- |
| PostgreSQL (primary transactional DB) | <= 15 minutes | <= 60 minutes | Backend + Platform on-call |
| Artifact object storage | <= 15 minutes | <= 120 minutes | Platform on-call |
| Runtime secrets/configuration | <= 60 minutes | <= 45 minutes | Security + Platform on-call |
| DNS + ingress routing | N/A (control-plane) | <= 30 minutes | Platform on-call |

### Target interpretation

- **RPO** is measured by the age of last recoverable write.
- **RTO** is measured from incident declaration to first successful customer write/read in production.
- Missing an RPO/RTO target requires a Sev-1 escalation and retrospective corrective action within 30 days.

## Backup retention policy

- **PostgreSQL full backups:** daily, retain 35 days.
- **PostgreSQL weekly checkpoints:** retain 12 weeks.
- **PostgreSQL monthly checkpoints:** retain 12 months.
- **WAL archive segments:** retain 35 days minimum (to support PITR across full backup windows).
- **Object storage current versions:** retained per product/legal policy.
- **Object storage non-current versions:** retain 90 days minimum.
- **Object storage deleted-marker cleanup:** purge after 30 days to limit orphaned version metadata.

## Non-production restore validation drills

- Run restore drills at least **quarterly** in non-production.
- Use the restore checklist in `restore-validation-checklist.md`.
- Persist drill evidence (timestamps, query outputs, object checksum samples, screenshots/log excerpts) in the incident knowledge base.
- Track: achieved RPO, achieved RTO, gaps, and owner/due-date for corrective actions.

## Scripted backup entry points

- `scripts/backup/run_pg_full_backup.sh`
- `scripts/backup/run_pg_wal_archive.sh`

Required environment variables:

- `DATABASE_URL` for full backups
- `WAL_SOURCE_DIR` for WAL archive uploads
- `PG_BACKUP_BUCKET`
- `AWS_REGION`

## Playbook index

- [PostgreSQL restore playbook](./playbook-db-restore.md)
- [Secrets recovery playbook](./playbook-secrets-recovery.md)
- [Object storage assumptions + recovery playbook](./playbook-storage-recovery.md)
- [DNS/Ingress recovery playbook](./playbook-dns-ingress-recovery.md)
- [Key dependency outage playbook](./playbook-dependency-outages.md)
- [Restore validation checklist (non-prod drills)](./restore-validation-checklist.md)
