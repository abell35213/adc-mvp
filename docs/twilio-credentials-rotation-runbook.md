# Twilio Credentials Rotation Runbook

## Scope
Rotate Twilio keys used by OTP and notifications:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_VERIFY_SERVICE_SID`
- `TWILIO_SMS_FROM`
- `TWILIO_VOICE_FROM`

## Preconditions
- Twilio Console admin access.
- Access to AWS Secrets Manager runtime secret.
- Ability to restart backend + worker.

## Procedure
1. In Twilio Console, create/regenerate the new auth token and verify service details.
2. Update AWS Secrets Manager JSON payload with new Twilio values.
3. Promote new secret version to `AWSCURRENT`.
4. Restart backend and worker deployments.
5. Execute test OTP send + verify flows and notification send task.

## Verification
- OTP request endpoint succeeds.
- OTP verification endpoint succeeds.
- Alert delivery task emits no Twilio auth errors.

## Rollback
1. Revert Twilio values to previous known-good secret version.
2. Move `AWSCURRENT` label back.
3. Restart backend and worker.
