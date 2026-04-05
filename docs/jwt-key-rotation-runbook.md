# JWT Key Rotation Runbook

## Scope
Rotate `JWT_SECRET_KEY` used by backend token signing/verification.

## Preconditions
- Access to AWS Secrets Manager secret used by `AWS_SECRETS_MANAGER_SECRET_ID`.
- Ability to deploy backend + worker.
- Planned maintenance window (JWT revocation event).

## Procedure
1. Generate a new random signing key (at least 256 bits).
2. Update the runtime secret JSON in AWS Secrets Manager:
   - Replace `JWT_SECRET_KEY`.
   - Keep other keys unchanged.
3. Move staging label (`AWSCURRENT` by default) to the new version.
4. Roll backend and worker deployments so they reload settings.
5. Invalidate active sessions if policy requires forced re-authentication.

## Verification
- Confirm `/health` (or app readiness) is green after rollout.
- Perform login and confirm newly minted JWTs validate.
- Confirm old JWTs are rejected if forced session invalidation was performed.

## Rollback
1. Move `AWSCURRENT` back to prior secret version.
2. Restart backend and worker.
3. Validate login/token flows.
