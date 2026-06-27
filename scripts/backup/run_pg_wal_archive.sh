#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
WAL_SOURCE_DIR="${WAL_SOURCE_DIR:?WAL_SOURCE_DIR is required}"
PG_BACKUP_BUCKET="${PG_BACKUP_BUCKET:?PG_BACKUP_BUCKET is required}"
AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
BACKUP_PREFIX="${BACKUP_PREFIX:-postgres/wal}"

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" != "1" ]]; then
    "$@"
  fi
}

shopt -s nullglob
wal_files=("${WAL_SOURCE_DIR}"/*)
if (( ${#wal_files[@]} == 0 )); then
  echo "No WAL files found in ${WAL_SOURCE_DIR}"
  exit 0
fi

for wal_file in "${wal_files[@]}"; do
  wal_name="$(basename "$wal_file")"
  s3_uri="s3://${PG_BACKUP_BUCKET}/${BACKUP_PREFIX}/${wal_name}"
  run aws s3 cp "$wal_file" "$s3_uri" --region "$AWS_REGION"
done
