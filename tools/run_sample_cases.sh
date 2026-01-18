#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(pwd)}"
CASES_DIR="$ROOT_DIR/samples/cases"
DB_PREFIX="${HB_LOOP_DB_PREFIX:-/tmp/hb_loop_}"
REPORTS_PREFIX="${HB_LOOP_REPORTS_PREFIX:-/tmp/hb_loop_reports_}"

if [[ ! -d "$CASES_DIR" ]]; then
  echo "missing cases dir: $CASES_DIR" >&2
  exit 1
fi

for case_dir in "$CASES_DIR"/*; do
  [[ -d "$case_dir" ]] || continue
  name="$(basename "$case_dir")"
  baseline_source="$case_dir/baseline_source.csv"
  current_source="$case_dir/current_source.csv"
  baseline_meta="$case_dir/baseline_run_meta.json"
  current_meta="$case_dir/current_run_meta.json"
  db_path="${DB_PREFIX}${name}.db"
  reports_dir="${REPORTS_PREFIX}${name}"

  echo "=== $name: baseline ==="
  "$ROOT_DIR/bin/hb" run --source pba_excel "$baseline_source" --run-meta "$baseline_meta" --db "$db_path" --reports "$reports_dir"
  echo "=== $name: current ==="
  "$ROOT_DIR/bin/hb" run --source pba_excel "$current_source" --run-meta "$current_meta" --db "$db_path" --reports "$reports_dir"
  echo ""
done

open_cmd=""
if command -v open >/dev/null 2>&1; then
  open_cmd="open"
elif command -v xdg-open >/dev/null 2>&1; then
  open_cmd="xdg-open"
fi

reports=()
while IFS= read -r -d '' report; do
  if [[ "$(basename "$(dirname "$report")")" == *_current ]]; then
    reports+=("$report")
  fi
done < <(find "${REPORTS_PREFIX}"* -type f -name "drift_report.html" -print0 2>/dev/null)

if [[ -z "$open_cmd" ]]; then
  echo "No open/xdg-open found. Reports are under ${REPORTS_PREFIX}*" >&2
  exit 0
fi

if [[ ${#reports[@]} -eq 0 ]]; then
  echo "No current drift reports found under ${REPORTS_PREFIX}*" >&2
  exit 0
fi

echo "Opening ${#reports[@]} reports via $open_cmd..."
for report in "${reports[@]}"; do
  "$open_cmd" "$report"
done
