# AWS ECS / Fargate Pilot Deployment Guide

This is the primary controlled-pilot deployment path. Existing Kubernetes / GHCR assets in `infra/production/` and `scripts/deploy_hooks.sh` are legacy references and are not the recommended pilot target.

## Architecture

- **API service**: FastAPI container from `backend/Dockerfile`, fronted by an ALB, health checks on `/health/live` and `/health/ready`.
- **Worker service**: Celery worker from the same backend image, separate ECS service, no public ingress.
- **Database**: PostgreSQL on Amazon RDS.
- **Queue/cache**: Redis or Valkey on Amazon ElastiCache.
- **Artifact storage**: S3 buckets for artifacts and exports.
- **Secrets**: AWS Secrets Manager JSON secret consumed via environment-variable mapping.
- **Logs/metrics**: CloudWatch Logs for API, worker, and one-off migration tasks.
- **Frontend**: Deploy the Next.js web app to Vercel, Amplify Hosting, or ECS behind the same ALB; keep `NEXT_PUBLIC_API_BASE_URL` aligned with the API domain.

## Required AWS resources

- ECR repositories: `<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/adc-api` and `adc-frontend`
- ECS cluster: `<ADC_ECS_CLUSTER>`
- ECS services: `<ADC_API_SERVICE>`, `<ADC_WORKER_SERVICE>`
- ECS task execution role: `<ADC_TASK_EXECUTION_ROLE_ARN>`
- ECS task role: `<ADC_TASK_ROLE_ARN>`
- RDS endpoint in `DATABASE_URL`
- Redis / Valkey endpoint in `REDIS_URL`
- S3 buckets: `<ADC_ARTIFACTS_BUCKET>`, `<ADC_EXPORTS_BUCKET>`, optional `<ADC_PG_BACKUP_BUCKET>`
- Secrets Manager secret ARN: `<ADC_RUNTIME_SECRET_ARN>`
- CloudWatch log groups: `/aws/ecs/adc-api`, `/aws/ecs/adc-worker`, `/aws/ecs/adc-migrations`

## Image build / tag / push

```bash
export AWS_REGION=<REGION>
export AWS_ACCOUNT_ID=<ACCOUNT_ID>
export ECR_API_REPOSITORY=adc-api
export ECR_FRONTEND_REPOSITORY=adc-frontend
export IMAGE_TAG=$(git rev-parse --short HEAD)
scripts/deploy/build_and_push_ecr.sh
```

The script logs in to ECR, builds the backend and frontend images, tags them with `${IMAGE_TAG}`, and pushes them without printing secrets.

## Task definition requirements

Use the skeletons under `infra/aws/ecs/` and replace every `<PLACEHOLDER>` value.

### API task

- Container image: `<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/adc-api:<IMAGE_TAG>`
- Command: default `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Port mapping: `8000/tcp`
- Health check: `curl --fail --silent http://127.0.0.1:8000/health/live || exit 1`
- Environment: `APP_ENV=staging`, `SECRET_PROVIDER=aws_secrets_manager`, `AWS_REGION=<REGION>`, `RELEASE=<IMAGE_TAG>`
- Secrets: `AWS_SECRETS_MANAGER_SECRET_ID`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `OTP_HASH_PEPPER`, `TWILIO_*`, `SAMSARA_API_KEY`, `S3_*`

### Worker task

- Same image as API
- Command: `celery -A app.tasks.celery_app worker --loglevel=info`
- No ALB target group
- Same runtime secret set as API
- Separate CloudWatch log group stream prefix

## Secrets Manager mapping

Store one JSON object in Secrets Manager with keys matching the backend settings names, for example:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `OTP_HASH_PEPPER`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_VERIFY_SERVICE_SID`
- `SAMSARA_API_KEY`
- `S3_ARTIFACTS_BUCKET`
- `S3_EXPORTS_BUCKET`

The backend already supports `SECRET_PROVIDER=aws_secrets_manager` and `AWS_SECRETS_MANAGER_SECRET_ID=<SECRET_NAME_OR_ARN>`.

## RDS / Redis / S3 requirements

- **RDS**: allow ingress from the ECS service security groups only; use TLS-capable connection strings where required by policy.
- **Redis / Valkey**: allow ingress from the ECS service security groups only; low-latency network placement matters for Celery throughput.
- **S3 permissions**: task role needs `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`, and presign-related access for the artifacts and exports buckets.

## CloudWatch logging

- API logs: `/aws/ecs/adc-api`
- Worker logs: `/aws/ecs/adc-worker`
- Migrations logs: `/aws/ecs/adc-migrations`
- Retention: at least 30 days for staging; longer if pilot policy requires it.

## ALB, CORS, and cookies

- ALB target group health check path: `/health/ready`
- Frontend origin must match `FRONTEND_ORIGIN`
- If frontend and API are on different subdomains, set `COOKIE_DEPLOYMENT_TOPOLOGY=cross_site` and `COOKIE_SECURE=true`
- Do not enable `PDF_RENDER_FAIL_OPEN` in staging or production-like environments

## Migration strategy

Run migrations as a one-off ECS task before rolling out API or worker containers.

```bash
export AWS_REGION=<REGION>
export ECS_CLUSTER=<ADC_ECS_CLUSTER>
export MIGRATION_TASK_DEFINITION=<ADC_API_TASK_DEFINITION>
export ECS_SUBNETS=subnet-aaaa,subnet-bbbb
export ECS_SECURITY_GROUPS=sg-aaaa
scripts/deploy/run_migrations_ecs.sh
```

Never rely on multiple API tasks auto-running migrations concurrently.

## Deployment sequence

1. Build and push backend/frontend images to ECR.
2. Back up the database.
3. Run migrations as a one-off ECS task.
4. Register updated API and worker task definitions.
5. Update the API ECS service and wait for steady state.
6. Update the worker ECS service and wait for steady state.
7. Run staging smoke tests.
8. Capture evidence in the release ticket.

## Staging smoke tests

```bash
export STAGING_API_BASE_URL=https://<API_DOMAIN>
export STAGING_FRONTEND_URL=https://<FRONTEND_DOMAIN>
export STAGING_READY_URL=https://<API_DOMAIN>/health/ready
scripts/deploy/smoke_staging.sh
```

The smoke script checks API liveness/readiness, frontend reachability when configured, and safe anonymous endpoints only.

## Rollback

- Re-run the prior task definition revision for API and worker.
- If a migration is not backward-compatible, restore from backup before reintroducing the previous application version.
- Use `docs/operations/restore-drill.md` for restore validation steps.
