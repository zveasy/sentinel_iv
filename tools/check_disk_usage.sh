#!/usr/bin/env bash
set -euo pipefail

REPORTS_DIR="${1:-mvp/reports}"
DB_PATH="${2:-runs.db}"
MAX_MB="${3:-5120}"

if [[ ! -d "$REPORTS_DIR" ]]; then
  echo "reports dir not found: $REPORTS_DIR" >&2
  exit 2
fi

REPORTS_MB=$(du -sk "$REPORTS_DIR" | awk '{print int($1/1024)}')
DB_MB=0
if [[ -f "$DB_PATH" ]]; then
  DB_MB=$(du -sk "$DB_PATH" | awk '{print int($1/1024)}')
fi

TOTAL_MB=$((REPORTS_MB + DB_MB))
if [[ "$TOTAL_MB" -gt "$MAX_MB" ]]; then
  echo "disk usage alert: ${TOTAL_MB}MB exceeds ${MAX_MB}MB (reports=${REPORTS_MB}MB, db=${DB_MB}MB)" >&2
  exit 1
fi

echo "ok: disk usage ${TOTAL_MB}MB (reports=${REPORTS_MB}MB, db=${DB_MB}MB)"
