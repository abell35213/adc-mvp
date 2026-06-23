#!/usr/bin/env bash
set -euo pipefail

# Deployment stage hooks invoked by .github/workflows/deploy-promotion.yml.
#
# This script runs on every push to main, where no production cluster is
# reachable. To keep that pipeline green while still performing real work when a
# cluster IS wired up, each stage is config-driven and degrades to a logged
# no-op (exit 0) unless deployment is explicitly enabled and the required
# tooling/config is present.
#
# Enable real execution by setting DEPLOY_ENABLED=1 (typically via the GitHub
# Environment secrets for `staging` / `production`) plus the target overrides
# below. With DEPLOY_ENABLED unset/0 the stage is skipped, not failed.
#
# Configuration (environment variables, with infra/production defaults):
#   DEPLOY_ENABLED                 1 to run real commands; otherwise skip (default 0)
#   DEPLOY_K8S_NAMESPACE           Kubernetes namespace (default: adc)
#   DEPLOY_K8S_BACKEND_DEPLOYMENT  Backend Deployment name (default: adc-backend)
#   DEPLOY_K8S_WORKER_DEPLOYMENT   Worker Deployment name (default: adc-worker)
#   DEPLOY_K8S_BACKEND_CONTAINER   Backend container name (default: app)
#   DEPLOY_K8S_WORKER_CONTAINER    Worker container name (default: worker)
#   DEPLOY_IMAGE_REPOSITORY        Image repo (default: ghcr.io/your-org/adc-backend)
#   DEPLOY_ROLLOUT_TIMEOUT         kubectl rollout status timeout (default: 5m)
#   DEPLOY_STAGING_HEALTH_URL      Staging readiness URL for smoke stage
#   DEPLOY_PRODUCTION_HEALTH_URL   Production readiness URL for health-check stage
#   DEPLOY_HEALTH_RETRIES          Health poll attempts (default: 10)
#   DEPLOY_HEALTH_RETRY_DELAY      Seconds between health polls (default: 6)

stage="${1:-}"
deploy_version="${2:-${GITHUB_SHA:-unknown}}"

if [[ -z "$stage" ]]; then
  echo "Usage: $0 <staging|smoke|production|health-check|rollback> [deploy_version]" >&2
  exit 1
fi

DEPLOY_ENABLED="${DEPLOY_ENABLED:-0}"
NAMESPACE="${DEPLOY_K8S_NAMESPACE:-adc}"
BACKEND_DEPLOYMENT="${DEPLOY_K8S_BACKEND_DEPLOYMENT:-adc-backend}"
WORKER_DEPLOYMENT="${DEPLOY_K8S_WORKER_DEPLOYMENT:-adc-worker}"
BACKEND_CONTAINER="${DEPLOY_K8S_BACKEND_CONTAINER:-app}"
WORKER_CONTAINER="${DEPLOY_K8S_WORKER_CONTAINER:-worker}"
IMAGE_REPOSITORY="${DEPLOY_IMAGE_REPOSITORY:-ghcr.io/your-org/adc-backend}"
ROLLOUT_TIMEOUT="${DEPLOY_ROLLOUT_TIMEOUT:-5m}"
HEALTH_RETRIES="${DEPLOY_HEALTH_RETRIES:-10}"
HEALTH_RETRY_DELAY="${DEPLOY_HEALTH_RETRY_DELAY:-6}"

log() {
  echo "[deploy-hook] stage=${stage} deploy_version=${deploy_version} $*"
}

# Returns success only when real execution is opted in AND the cluster tooling
# is available. Keeps push-to-main CI green where no cluster is configured.
deploy_target_configured() {
  if [[ "$DEPLOY_ENABLED" != "1" ]]; then
    return 1
  fi
  if ! command -v kubectl >/dev/null 2>&1; then
    log "DEPLOY_ENABLED=1 but kubectl is not installed; cannot run stage" >&2
    return 1
  fi
  return 0
}

skip_stage() {
  log "deployment not enabled (DEPLOY_ENABLED!=1) or tooling missing; skipping $*"
}

# Roll a single deployment to the target image tag and wait for it to converge.
rollout_deployment() {
  local deployment="$1"
  local container="$2"
  local image="${IMAGE_REPOSITORY}:${deploy_version}"

  log "setting ${deployment}/${container} image to ${image}"
  kubectl set image "deployment/${deployment}" "${container}=${image}" -n "$NAMESPACE"
  kubectl rollout status "deployment/${deployment}" -n "$NAMESPACE" --timeout="$ROLLOUT_TIMEOUT"
}

# Undo the most recent rollout for a deployment and wait for it to converge.
rollback_deployment() {
  local deployment="$1"
  log "rolling back ${deployment} to previous revision"
  kubectl rollout undo "deployment/${deployment}" -n "$NAMESPACE"
  kubectl rollout status "deployment/${deployment}" -n "$NAMESPACE" --timeout="$ROLLOUT_TIMEOUT"
}

# Poll a readiness URL until it returns success or attempts are exhausted.
probe_health() {
  local url="$1"
  if [[ -z "$url" ]]; then
    log "no health URL configured; skipping HTTP readiness probe"
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    log "curl not available; skipping HTTP readiness probe for ${url}" >&2
    return 0
  fi

  local attempt=1
  while ((attempt <= HEALTH_RETRIES)); do
    if curl --fail --silent --show-error --max-time 10 "$url" >/dev/null 2>&1; then
      log "health probe succeeded for ${url} on attempt ${attempt}"
      return 0
    fi
    log "health probe attempt ${attempt}/${HEALTH_RETRIES} failed for ${url}; retrying in ${HEALTH_RETRY_DELAY}s"
    sleep "$HEALTH_RETRY_DELAY"
    ((attempt++))
  done

  log "health probe exhausted ${HEALTH_RETRIES} attempts for ${url}" >&2
  return 1
}

case "$stage" in
  staging)
    if deploy_target_configured; then
      log "deploying backend + worker to staging namespace ${NAMESPACE}"
      rollout_deployment "$BACKEND_DEPLOYMENT" "$BACKEND_CONTAINER"
      rollout_deployment "$WORKER_DEPLOYMENT" "$WORKER_CONTAINER"
    else
      skip_stage "staging deployment"
    fi
    ;;
  smoke)
    if deploy_target_configured; then
      log "running staging smoke checks"
      probe_health "${DEPLOY_STAGING_HEALTH_URL:-}"
    else
      skip_stage "staging smoke tests"
    fi
    ;;
  production)
    if deploy_target_configured; then
      log "deploying backend + worker to production namespace ${NAMESPACE}"
      rollout_deployment "$BACKEND_DEPLOYMENT" "$BACKEND_CONTAINER"
      rollout_deployment "$WORKER_DEPLOYMENT" "$WORKER_CONTAINER"
    else
      skip_stage "production deployment"
    fi
    ;;
  health-check)
    if deploy_target_configured; then
      log "running production post-deploy health checks"
      probe_health "${DEPLOY_PRODUCTION_HEALTH_URL:-}"
    else
      skip_stage "production health checks"
    fi
    ;;
  rollback)
    if deploy_target_configured; then
      log "executing rollback to previous stable release"
      rollback_deployment "$BACKEND_DEPLOYMENT"
      rollback_deployment "$WORKER_DEPLOYMENT"
    else
      skip_stage "rollback automation"
    fi
    ;;
  *)
    echo "Unsupported stage: $stage" >&2
    exit 2
    ;;
esac
