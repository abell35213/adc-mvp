# Playbook: PostgreSQL Restore

## Trigger conditions

- Database corruption.
- Accidental destructive write.
- Region/instance outage.
- Sustained replication failure with data divergence risk.

## Preconditions

- Incident declared and IC assigned.
- Write freeze approved (application maintenance mode or write-block controls).
- Target recovery timestamp selected.

## Procedure

1. Confirm latest healthy full backup and WAL archive continuity.
2. Provision restore database from full backup.
3. Apply WAL to target recovery timestamp (PITR).
4. Run schema integrity check (`alembic current`) and critical query smoke tests.
5. Point staging/test clients at restored DB for confidence checks.
6. Promote restored DB to primary.
7. Update `DATABASE_URL` secret stage/reference and restart backend + workers.
8. Observe error rates, migration state, and background task behavior for 30 minutes.

## Validation

- API read/write smoke tests pass.
- Job queue throughput returns to baseline.
- No migration drift.
- RPO <= 15 minutes and RTO <= 60 minutes.

## Rollback strategy

- If restored primary is unhealthy, revert `DATABASE_URL` reference to prior stable primary.
- Keep restored instance online for forensic comparison.
