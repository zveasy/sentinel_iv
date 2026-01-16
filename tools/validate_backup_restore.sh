#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-runs.db}"
WORK_DIR="${2:-backups/validation}"
ENCRYPT_KEY="${3:-}"

mkdir -p "$WORK_DIR"

BACKUP_PATH="$WORK_DIR/runs.db.backup"
RESTORED_PATH="$WORK_DIR/runs_restored.db"
ENC_PATH="$WORK_DIR/runs_encrypted.db"
DEC_PATH="$WORK_DIR/runs_decrypted.db"

if [[ ! -f "$DB_PATH" ]]; then
  echo "db not found: $DB_PATH" >&2
  exit 2
fi

cp "$DB_PATH" "$BACKUP_PATH"
echo "backup created: $BACKUP_PATH"

tools/restore_registry.sh "$BACKUP_PATH" "$RESTORED_PATH" >/dev/null

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$RESTORED_PATH" "SELECT count(*) FROM runs;" >/dev/null
  echo "restore validation ok"
else
  echo "sqlite3 not found; skipped restore query validation" >&2
fi

if [[ -n "$ENCRYPT_KEY" ]]; then
  if command -v sqlcipher >/dev/null 2>&1; then
    tools/sqlcipher_encrypt_db.sh "$DB_PATH" "$ENC_PATH" "$ENCRYPT_KEY" >/dev/null
    tools/sqlcipher_decrypt_db.sh "$ENC_PATH" "$DEC_PATH" "$ENCRYPT_KEY" >/dev/null
    if command -v sqlite3 >/dev/null 2>&1; then
      sqlite3 "$DEC_PATH" "SELECT count(*) FROM runs;" >/dev/null
    fi
    echo "encrypted restore validation ok"
  else
    echo "sqlcipher not found; skipped encrypted validation" >&2
  fi
fi

echo "backup/restore validation complete"
