# Phase 1 Infrastructure Inventory
- Staging Redis is ElastiCache Serverless (Valkey-compatible endpoint)
- Current backend code still contains legacy S3_BUCKET references; temporary compatibility field retained in AppSettings
- Frontend env uses NEXT_PUBLIC_API_BASE_URL and optional API_INTERNAL_BASE_URL
- Root .env.example is reference-only; service-specific templates live under backend/, frontend/, and driver-app/

## Region
us-east-1

## AWS Account Model
Single account with separate staging and prod resources

## ECR
- adc-backend

## RDS
- staging identifier: adc-staging-rds-postgres
- staging endpoint: adc-staging-rds-postgres.cqf26iq8k2pg.us-east-1.rds.amazonaws.com
- prod identifier: adc-prod-rds-postgres
- database name: postgres
- app database target: adc_mvp
- port: 5432

## Redis / Valkey / ElastiCache
- staging identifier: adc-staging-redis
- staging endpoint: adc-staging-redis-5kktzo.serverless.use1.cache.amazonaws.com
- port: 6379
- engine: Valkey
- deployment type: serverless
- prod identifier: adc-prod-redis

## S3
- adc-staging-artifacts
- adc-staging-exports
- adc-prod-artifacts
- adc-prod-exports

## Secrets Manager
- adc/staging/runtime
- adc/prod/runtime

## IAM Roles
- adc-ecs-task-execution-role
- adc-ecs-app-runtime-role

## IAM Policies
- adc-staging-app-runtime-policy

## Security Groups
- adc-alb-sg
- adc-api-sg
- adc-worker-sg
- adc-rds-sg
- adc-redis-sg

## Domains
- staging-app.yourdomain.com
- staging-api.yourdomain.com
- app.yourdomain.com
- api.yourdomain.com

## Notes
- Staging DATABASE_URL currently points to RDS host in us-east-1
- Staging REDIS_URL currently points to ElastiCache serverless endpoint in us-east-1
- Secrets created in Secrets Manager
- S3 buckets created
- ECS roles created
