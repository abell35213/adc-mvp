# DB Credentials Rotation Runbook

## Scope
Rotate `DATABASE_URL` credential for PostgreSQL.

## Preconditions
- Database admin access.
- Dual-user or phased password rotation plan.
- Access to AWS Secrets Manager runtime secret.

## Procedure
1. Create a new DB credential (new password or new service user).
2. Validate connectivity from a staging shell/client.
3. Update `DATABASE_URL` in AWS Secrets Manager JSON.
4. Promote updated secret version to `AWSCURRENT`.
5. Roll backend and worker deployments.
6. Confirm migrations and app queries succeed.
7. Decommission old DB credential.

## Verification
- Backend starts without DB auth errors.
- Read/write smoke tests pass.
- Worker tasks touching DB complete.

## Rollback
1. Restore prior `DATABASE_URL` version label.
2. Restart backend and worker.
3. Re-enable old DB credential if disabled.
