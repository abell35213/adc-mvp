#!/usr/bin/env bash
set -euo pipefail

# Redeploy-safe AWS Secrets Manager runtime secret rotation helper.
# Updates one or more keys as a staged secret version, validates JSON shape,
# promotes AWSCURRENT, and restarts backend + worker deployments.

usage() {
  cat <<'EOF'
Usage:
  scripts/rotate_runtime_secrets.sh \
    --secret-id <aws-secret-id> \
    --namespace <k8s-namespace> \
    --deployment <backend-deployment> \
    --worker-deployment <worker-deployment> \
    --set KEY=VALUE [--set KEY=VALUE ...] [--region us-east-1] [--dry-run]

Notes:
  - Designed for rotating: DATABASE_URL, REDIS_URL, S3_* buckets/keys,
    TWILIO_*, SAMSARA_API_KEY, JWT_SECRET_KEY, OTP_HASH_PEPPER.
  - Requires aws + jq + kubectl.
EOF
}

SECRET_ID=""
REGION="${AWS_REGION:-us-east-1}"
NAMESPACE=""
DEPLOYMENT=""
WORKER_DEPLOYMENT=""
DRY_RUN=0
UPDATES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --secret-id)
      SECRET_ID="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --deployment)
      DEPLOYMENT="$2"
      shift 2
      ;;
    --worker-deployment)
      WORKER_DEPLOYMENT="$2"
      shift 2
      ;;
    --set)
      UPDATES+=("$2")
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$SECRET_ID" || -z "$NAMESPACE" || -z "$DEPLOYMENT" || -z "$WORKER_DEPLOYMENT" || ${#UPDATES[@]} -eq 0 ]]; then
  usage
  exit 2
fi

for dep in aws jq kubectl; do
  if ! command -v "$dep" >/dev/null 2>&1; then
    echo "Missing required dependency: $dep" >&2
    exit 2
  fi
done

echo "Fetching AWSCURRENT for $SECRET_ID in $REGION..."
CURRENT_SECRET_JSON="$({ aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --version-stage AWSCURRENT \
  --region "$REGION" \
  --query SecretString \
  --output text; } )"

UPDATED_JSON="$CURRENT_SECRET_JSON"
for kv in "${UPDATES[@]}"; do
  key="${kv%%=*}"
  value="${kv#*=}"
  if [[ -z "$key" || "$key" == "$value" ]]; then
    echo "Invalid --set format: $kv (expected KEY=VALUE)" >&2
    exit 2
  fi
  UPDATED_JSON="$(jq --arg k "$key" --arg v "$value" '.[$k]=$v' <<<"$UPDATED_JSON")"
done

# Validate JSON is still an object and key set exists.
jq -e 'type == "object"' <<<"$UPDATED_JSON" >/dev/null
for required_key in DATABASE_URL REDIS_URL S3_ARTIFACTS_BUCKET S3_EXPORTS_BUCKET TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_VERIFY_SERVICE_SID SAMSARA_API_KEY JWT_SECRET_KEY OTP_HASH_PEPPER; do
  jq -e --arg k "$required_key" '.[$k] != null and (.[$k] | tostring | length > 0)' <<<"$UPDATED_JSON" >/dev/null || {
    echo "Guardrail failure: required runtime secret missing/empty after update: $required_key" >&2
    exit 3
  }
done

if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry-run mode enabled. Updated secret payload preview (values redacted):"
  jq 'with_entries(.value = "***redacted***")' <<<"$UPDATED_JSON"
  exit 0
fi

echo "Creating new secret version..."
NEW_VERSION_ID="$(aws secretsmanager put-secret-value \
  --secret-id "$SECRET_ID" \
  --secret-string "$UPDATED_JSON" \
  --region "$REGION" \
  --query VersionId \
  --output text)"

echo "Promoting version $NEW_VERSION_ID to AWSCURRENT..."
PREVIOUS_VERSION_ID="$(aws secretsmanager list-secret-version-ids \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query 'Versions[?contains(VersionStages, `AWSCURRENT`)].VersionId | [0]' \
  --output text)"

aws secretsmanager update-secret-version-stage \
  --secret-id "$SECRET_ID" \
  --version-stage AWSCURRENT \
  --move-to-version-id "$NEW_VERSION_ID" \
  --remove-from-version-id "$PREVIOUS_VERSION_ID" \
  --region "$REGION" >/dev/null

echo "Restarting deployments for redeploy-safe secret pickup..."
kubectl rollout restart "deployment/$DEPLOYMENT" -n "$NAMESPACE"
kubectl rollout restart "deployment/$WORKER_DEPLOYMENT" -n "$NAMESPACE"

kubectl rollout status "deployment/$DEPLOYMENT" -n "$NAMESPACE" --timeout=5m
kubectl rollout status "deployment/$WORKER_DEPLOYMENT" -n "$NAMESPACE" --timeout=5m

echo "Rotation complete. Validate /health, OTP flow, Samsara sync, and storage uploads before revoking old credentials."
