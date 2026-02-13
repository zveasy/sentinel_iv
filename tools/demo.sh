#!/usr/bin/env bash
# Run a quick Harmony Bridge demo: baseline + current run, then open the drift report.
# Usage: from repo root, run:  ./tools/demo.sh
#        or:                   ./tools/demo.sh --no-open   (do not open browser)

set -euo pipefail

ROOT="${ROOT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CASE="${DEMO_CASE:-single_metric_drift}"
OUT="${DEMO_OUT:-$ROOT/demo_output}"
DB="$OUT/demo.db"
REPORTS="$OUT/reports"
OPEN_REPORT="${OPEN_REPORT:-1}"

for arg in "$@"; do
  if [[ "$arg" == "--no-open" ]]; then
    OPEN_REPORT=0
  fi
done

cd "$ROOT"
mkdir -p "$OUT"

echo "=== Harmony Bridge demo: $CASE ==="
BASELINE_SOURCE="$ROOT/samples/cases/$CASE/baseline_source.csv"
CURRENT_SOURCE="$ROOT/samples/cases/$CASE/current_source.csv"
BASELINE_META="$ROOT/samples/cases/$CASE/baseline_run_meta.json"
CURRENT_META="$ROOT/samples/cases/$CASE/current_run_meta.json"

if [[ ! -f "$BASELINE_SOURCE" ]] || [[ ! -f "$CURRENT_SOURCE" ]]; then
  echo "Missing sample data: $BASELINE_SOURCE or $CURRENT_SOURCE" >&2
  exit 1
fi

echo "1) Ingest + analyze baseline..."
"$ROOT/bin/hb" run --source pba_excel "$BASELINE_SOURCE" \
  --run-meta "$BASELINE_META" \
  --db "$DB" \
  --reports "$REPORTS" \
  --out "$OUT/baseline"

echo ""
echo "2) Ingest + analyze current (vs baseline)..."
"$ROOT/bin/hb" run --source pba_excel "$CURRENT_SOURCE" \
  --run-meta "$CURRENT_META" \
  --db "$DB" \
  --reports "$REPORTS" \
  --out "$OUT/current"

# Prefer the "current" run report (shows drift vs baseline)
REPORT_HTML=""
for dir in "$REPORTS"/*/; do
  if [[ -f "${dir}drift_report.html" && "$dir" == *current* ]]; then
    REPORT_HTML="${dir}drift_report.html"
    break
  fi
done
if [[ -z "$REPORT_HTML" ]]; then
  for dir in "$REPORTS"/*/; do
    if [[ -f "${dir}drift_report.html" ]]; then
      REPORT_HTML="${dir}drift_report.html"
      break
    fi
  done
fi
if [[ -z "$REPORT_HTML" ]]; then
  REPORT_HTML=$(find "$REPORTS" -name "drift_report.html" -type f 2>/dev/null | head -1)
fi

echo ""
if [[ -n "$REPORT_HTML" && -f "$REPORT_HTML" ]]; then
  echo "Report: $REPORT_HTML"
  echo "JSON:  ${REPORT_HTML%.html}.json"
  if [[ "$OPEN_REPORT" == "1" ]]; then
    if command -v open >/dev/null 2>&1; then
      open "$REPORT_HTML"
      echo "Opened report in browser."
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$REPORT_HTML"
      echo "Opened report in browser."
    else
      echo "To view the report, open: $REPORT_HTML"
    fi
  fi
else
  echo "Report not found under $REPORTS"
  exit 1
fi

echo ""
echo "Done. To run the local UI instead:  ./bin/hb ui   then open http://127.0.0.1:8765"
