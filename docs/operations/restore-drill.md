# Restore Drill

Use this document for staged non-production restore drills before the controlled pilot and at least quarterly afterward.

## Preconditions

- Latest successful full backup exists in S3.
- WAL archive objects exist for the target restore window.
- A non-production RDS restore target is available.
- Secrets Manager, S3, and ECS access are available to the operator.

## Drill steps

1. Record the start time.
2. Confirm the backup object to restore and the target recovery timestamp.
3. Restore the database into a non-production instance.
4. Replay WAL up to the target recovery point.
5. Point a staging or temporary API task at the restored database.
6. Run the verification commands below.
7. Record the end time, achieved RPO, achieved RTO, and any gaps.

## Verification commands

```bash
psql "$RESTORE_DATABASE_URL" -c 'select version_num from alembic_version;'
psql "$RESTORE_DATABASE_URL" -c 'select count(*) from incidents;'
psql "$RESTORE_DATABASE_URL" -c 'select count(*) from exports;'
AWS_REGION=<REGION> STAGING_API_BASE_URL=https://<RESTORED_API_DOMAIN> scripts/deploy/smoke_staging.sh
```

## Restore validation checklist

- Schema version matches the expected Alembic head.
- Recent incidents and exports are present.
- Sample artifact and export objects can be read from S3.
- `/health/live` returns `200`.
- `/health/ready` returns `200`.
- Pilot login and a safe read-only workflow succeed.
- Measured RPO is within 15 minutes.
- Measured RTO is within 60 minutes.

## Evidence to retain

- Restore start/end timestamps
- Backup object path and WAL range used
- SQL outputs
- Smoke-test output
- Any follow-up actions with owners and due dates
