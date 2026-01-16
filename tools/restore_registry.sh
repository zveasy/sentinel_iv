#!/usr/bin/env bash
set -euo pipefail

BACKUP_PATH="${1:-}"
OUTPUT_PATH="${2:-runs.db}"

if [[ -z "$BACKUP_PATH" ]]; then
  echo "usage: $0 <backup_path> [output_path]" >&2
  exit 2
fi

if [[ ! -f "$BACKUP_PATH" ]]; then
  echo "backup not found: $BACKUP_PATH" >&2
  exit 2
fi

if [[ -f "$OUTPUT_PATH" ]]; then
  TS=$(date +"%Y%m%d%H%M%S")
  mv "$OUTPUT_PATH" "$OUTPUT_PATH.bak.$TS"
  echo "existing output moved to $OUTPUT_PATH.bak.$TS"
fi

cp "$BACKUP_PATH" "$OUTPUT_PATH"
echo "restored db written to $OUTPUT_PATH"
