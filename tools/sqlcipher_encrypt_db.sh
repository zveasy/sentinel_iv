#!/usr/bin/env sh
set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: tools/sqlcipher_encrypt_db.sh <input_db> <output_db> <key>"
  exit 1
fi

INPUT_DB="$1"
OUTPUT_DB="$2"
KEY="$3"

if ! command -v sqlcipher >/dev/null 2>&1; then
  echo "sqlcipher not found. Install SQLCipher and try again."
  exit 1
fi

if [ -f "${OUTPUT_DB}" ]; then
  TS=$(date +"%Y%m%d%H%M%S")
  BACKUP="${OUTPUT_DB}.bak.${TS}"
  mv "${OUTPUT_DB}" "${BACKUP}"
  echo "existing output moved to ${BACKUP}"
fi

sqlcipher "${OUTPUT_DB}" <<SQL
PRAGMA key = '${KEY}';
ATTACH DATABASE '${INPUT_DB}' AS plaintext KEY '';
SELECT sqlcipher_export('main', 'plaintext');
DETACH DATABASE plaintext;
SQL

echo "encrypted db written to ${OUTPUT_DB}"
