#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
ECS_CLUSTER="${ECS_CLUSTER:?ECS_CLUSTER is required}"
MIGRATION_TASK_DEFINITION="${MIGRATION_TASK_DEFINITION:?MIGRATION_TASK_DEFINITION is required}"
ECS_SUBNETS="${ECS_SUBNETS:?ECS_SUBNETS is required}"
ECS_SECURITY_GROUPS="${ECS_SECURITY_GROUPS:?ECS_SECURITY_GROUPS is required}"

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

NETWORK_CONFIGURATION="awsvpcConfiguration={subnets=[$(printf '"%s"' "${ECS_SUBNETS//,/\" \"}" | sed 's/ /,/g')],securityGroups=[$(printf '"%s"' "${ECS_SECURITY_GROUPS//,/\" \"}" | sed 's/ /,/g')],assignPublicIp=DISABLED}"

echo "Running Alembic migrations as a one-off ECS task"
run aws ecs run-task \
  --region "$AWS_REGION" \
  --cluster "$ECS_CLUSTER" \
  --launch-type FARGATE \
  --task-definition "$MIGRATION_TASK_DEFINITION" \
  --network-configuration "$NETWORK_CONFIGURATION" \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","-c","alembic.ini","upgrade","head"]}]}'
