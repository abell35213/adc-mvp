# Operator Triage Runbook

## Failed exports

- Check export status and recent event timeline.
- Re-run only after identifying the failed dependency.
- Confirm S3 bucket access and worker health.

## Failed background jobs

- Inspect worker logs and queue backlog.
- Confirm Redis / Valkey connectivity.
- Validate task retries are not looping on a hard failure.

## Provider outage

- Confirm provider status page or API error trend.
- Pause non-critical retries if they amplify the outage.
- Notify pilot contacts when incident data may be delayed.

## Driver OTP failure

- Confirm Twilio Verify credentials and recent request rate limits.
- Check for bad phone normalization or expired challenge.
- Escalate to manual support if the driver is blocked at scene.

## S3 / presigned URL issue

- Verify bucket names, IAM permissions, and object existence.
- Confirm system clocks are in sync if signatures appear expired.
- Reissue the export only after access-path checks pass.

## Redis issue

- Check ElastiCache / Valkey health and connection saturation.
- Confirm API and worker services can resolve the endpoint.
- Expect rate-limit and Celery symptoms if Redis is unavailable.

## DB issue

- Confirm RDS availability and connection limits.
- Check migration state before restarting services.
- Use restore procedures only with incident-command approval.

## Frontend / API mismatch

- Confirm deployed frontend and API versions.
- Validate `NEXT_PUBLIC_API_BASE_URL` and CORS/cookie settings.
- Rebuild/redeploy only the drifted component when possible.

## Webhook / provider failure

- Check callback logs, signature validation, and secret rotation status.
- Confirm external provider retries are arriving.
- Capture representative request IDs before escalating.
