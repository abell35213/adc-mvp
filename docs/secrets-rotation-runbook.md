# Runtime Secrets Rotation Runbook (DB/Redis/S3/Twilio/Samsara/JWT/Signing)

## Scope
This runbook standardizes rotation for runtime secrets used by backend and worker:

- `DATABASE_URL`
- `REDIS_URL`
- `S3_ARTIFACTS_BUCKET`, `S3_EXPORTS_BUCKET` (+ optional AWS access keys when static creds are used)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, `TWILIO_SMS_FROM`, `TWILIO_VOICE_FROM`
- `SAMSARA_API_KEY`
- `JWT_SECRET_KEY` (token signing key)
- `OTP_HASH_PEPPER` (OTP/signing-adjacent secret material)

Use this together with service-specific runbooks in `docs/db-credentials-rotation-runbook.md`,
`docs/twilio-credentials-rotation-runbook.md`, `docs/api-keys-rotation-runbook.md`, and
`docs/jwt-key-rotation-runbook.md`.

## Preconditions
- AWS IAM access to read/write the runtime secret (`secretsmanager:GetSecretValue`, `PutSecretValue`, `UpdateSecretVersionStage`).
- Kubernetes access to restart backend and worker deployments.
- Canary/smoke-test plan available.
- Ability to rollback quickly to previous secret version.

## Redeploy-safe standard workflow
1. **Prepare new credentials/keys**
   - Create and stage new credentials in each provider.
   - Do **not** revoke old credentials yet.
2. **Dry-run merge and guardrails**
   - Use `scripts/rotate_runtime_secrets.sh --dry-run` to merge updated keys into the current JSON secret.
   - Guardrails enforce required keys are still present/non-empty.
3. **Promote new secret version**
   - Script writes a new secret version and moves `AWSCURRENT` to it.
4. **Roll backend + worker**
   - Script restarts both deployments and blocks until rollouts complete.
5. **Post-rotation verification**
   - API health/readiness green.
   - DB read/write smoke test.
   - Redis-backed rate limit and task queue behavior.
   - S3 upload/download path checks.
   - Twilio OTP send/verify and notification checks.
   - Samsara sync/check endpoint success.
   - Auth login/refresh using newly signed JWTs.
6. **Revoke prior credentials**
   - Revoke old provider credentials only after the verification window passes.

## Automation command
```bash
scripts/rotate_runtime_secrets.sh \
  --secret-id adc/runtime \
  --region us-east-1 \
  --namespace production \
  --deployment adc-backend \
  --worker-deployment adc-worker \
  --set DATABASE_URL='postgresql://svc_new:***@db.example.com/adc' \
  --set REDIS_URL='redis://:***@redis.example.com:6379/0' \
  --set TWILIO_AUTH_TOKEN='***' \
  --set SAMSARA_API_KEY='***' \
  --set JWT_SECRET_KEY='***' \
  --set OTP_HASH_PEPPER='***'
```

## Rollback
1. Move `AWSCURRENT` to prior version in AWS Secrets Manager.
2. Restart backend and worker deployments.
3. Re-run smoke tests.
4. Re-enable old provider credentials if already revoked.

## Notes
- `backend/app/config/validation.py` fails startup outside local when critical secrets are missing.
- Production startup also rejects insecure defaults and insecure cookie configuration.
