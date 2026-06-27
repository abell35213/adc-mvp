#!/usr/bin/env bash
set -euo pipefail

STAGING_API_BASE_URL="${STAGING_API_BASE_URL:?STAGING_API_BASE_URL is required}"
STAGING_READY_URL="${STAGING_READY_URL:-${STAGING_API_BASE_URL%/}/health/ready}"
STAGING_LIVE_URL="${STAGING_LIVE_URL:-${STAGING_API_BASE_URL%/}/health/live}"
STAGING_FRONTEND_URL="${STAGING_FRONTEND_URL:-}"

check() {
  local url="$1"
  echo "Checking ${url}"
  curl --fail --silent --show-error --max-time 15 "$url" >/dev/null
}

check "$STAGING_LIVE_URL"
check "$STAGING_READY_URL"

if [[ -n "$STAGING_FRONTEND_URL" ]]; then
  check "$STAGING_FRONTEND_URL"
fi
