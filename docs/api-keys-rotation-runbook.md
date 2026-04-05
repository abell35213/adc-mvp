# API Keys Rotation Runbook

## Scope
Rotate provider API keys stored in runtime secrets (for example `SAMSARA_API_KEY`).

## Preconditions
- Provider console access.
- Access to AWS Secrets Manager runtime secret.
- Observability access for provider integration errors.

## Procedure
1. Create a new key in the provider console.
2. Update corresponding key in AWS Secrets Manager JSON payload.
3. Promote new secret version to `AWSCURRENT`.
4. Restart backend and worker.
5. Run provider-specific smoke test (e.g., list vehicles/events).
6. Revoke old provider key only after successful verification.

## Verification
- API calls authenticate with no `401/403` failures.
- Background sync/task logs show successful calls.

## Rollback
1. Move `AWSCURRENT` to prior secret version.
2. Restart backend and worker.
3. Re-enable previous provider key if already revoked.
