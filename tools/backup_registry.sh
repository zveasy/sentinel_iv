#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: tools/backup_registry.sh <db_path> [backup_dir]"
  exit 1
fi

DB_PATH="$1"
BACKUP_DIR="${2:-backups}"
TS=$(date +"%Y%m%d%H%M%S")

mkdir -p "${BACKUP_DIR}"
cp "${DB_PATH}" "${BACKUP_DIR}/runs.db.${TS}.bak"
echo "backup written to ${BACKUP_DIR}/runs.db.${TS}.bak"
