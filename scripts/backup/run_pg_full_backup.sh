#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL is required}"
PG_BACKUP_BUCKET="${PG_BACKUP_BUCKET:?PG_BACKUP_BUCKET is required}"
AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
BACKUP_PREFIX="${BACKUP_PREFIX:-postgres/full}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
ARCHIVE_PATH="${TMP_DIR}/pg-full-${TIMESTAMP}.dump"
S3_URI="s3://${PG_BACKUP_BUCKET}/${BACKUP_PREFIX}/pg-full-${TIMESTAMP}.dump"

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

echo "Creating PostgreSQL full backup"
run pg_dump --format=custom --file "$ARCHIVE_PATH" "$DATABASE_URL"
run aws s3 cp "$ARCHIVE_PATH" "$S3_URI" --region "$AWS_REGION"
