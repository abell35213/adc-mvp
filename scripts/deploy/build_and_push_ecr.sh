#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required}"
ECR_API_REPOSITORY="${ECR_API_REPOSITORY:?ECR_API_REPOSITORY is required}"
ECR_FRONTEND_REPOSITORY="${ECR_FRONTEND_REPOSITORY:?ECR_FRONTEND_REPOSITORY is required}"
IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required}"

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

API_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_API_REPOSITORY}:${IMAGE_TAG}"
FRONTEND_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_FRONTEND_REPOSITORY}:${IMAGE_TAG}"

echo "Logging in to ECR in ${AWS_REGION}"
if [[ "$DRY_RUN" != "1" ]]; then
  aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
fi

run docker build -t "$API_IMAGE" backend
run docker build -t "$FRONTEND_IMAGE" frontend
run docker push "$API_IMAGE"
run docker push "$FRONTEND_IMAGE"
