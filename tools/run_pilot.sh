#!/usr/bin/env sh
# Turnkey pilot: ingest sample data, set baseline, run watch (or one-shot), generate weekly summary, output pilot report.
# Run in repo root. Usage: ./tools/run_pilot.sh [--once] [--out-dir /path] [--duration-sec 3600]
# Without --once: runs watch for duration (default 3600 sec = 1h) then generates summary and report.
# With --once: ingest + baseline + one analyze + summary + report (about 1 hour of hands-off for full run).

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

OUT_DIR="${OUT_DIR:-$REPO_ROOT/pilot_output}"
DURATION_SEC="${DURATION_SEC:-3600}"
ONCE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --once)      ONCE=1 ;;
    --out-dir)   OUT_DIR="$2"; shift ;;
    --duration-sec) DURATION_SEC="$2"; shift ;;
    *) ;;
  esac
  shift
done

mkdir -p "$OUT_DIR"
export HB_DB_PATH="$OUT_DIR/runs.db"
export HB_REPORTS_DIR="$OUT_DIR/reports"
SAMPLES="$REPO_ROOT/samples/cases"
BASELINE_CSV="$SAMPLES/no_drift_pass/current_source.csv"
BASELINE_META="$SAMPLES/no_drift_pass/current_run_meta.json"
CURRENT_CSV="$SAMPLES/single_metric_drift/current_source.csv"
CURRENT_META="$SAMPLES/single_metric_drift/current_run_meta.json"

echo "Pilot: OUT_DIR=$OUT_DIR HB_DB_PATH=$HB_DB_PATH"

# 1) Ingest sample data (baseline run)
if [ ! -f "$BASELINE_CSV" ]; then
  echo "Missing sample: $BASELINE_CSV. Run from repo root with samples/cases populated."
  exit 1
fi
python -m hb.cli run --source pba_excel "$BASELINE_CSV" --run-meta "$BASELINE_META" --db "$HB_DB_PATH" --reports "$HB_REPORTS_DIR" || true
# Get last run_id for baseline tag (assume last run is the one we just created)
BASELINE_RUN_ID=$(python -c "
import sqlite3, os
conn = sqlite3.connect(os.environ['HB_DB_PATH'])
r = conn.execute('SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1').fetchone()
print(r[0] if r else '')
conn.close()
")
if [ -n "$BASELINE_RUN_ID" ]; then
  python -m hb.cli baseline set "$BASELINE_RUN_ID" --tag golden --db "$HB_DB_PATH"
  echo "Baseline set: $BASELINE_RUN_ID"
fi

# 2) Current run (with drift) or watch
if [ -n "$ONCE" ]; then
  python -m hb.cli run --source pba_excel "$CURRENT_CSV" --run-meta "$CURRENT_META" --db "$HB_DB_PATH" --reports "$HB_REPORTS_DIR" || true
else
  echo "Starting watch for ${DURATION_SEC}s (Ctrl+C to stop early)..."
  python -m hb.cli watch --dir "$REPO_ROOT/samples/cases/single_metric_drift" --source pba_excel --pattern "*.csv" --interval "$DURATION_SEC" --workspace "$OUT_DIR" --once 2>/dev/null || true
  # Or run a single current run for weekly summary
  python -m hb.cli run --source pba_excel "$CURRENT_CSV" --run-meta "$CURRENT_META" --db "$HB_DB_PATH" --reports "$HB_REPORTS_DIR" || true
fi

# 3) Weekly summary (list runs + last report status)
echo ""
echo "--- Pilot runs ---"
python -m hb.cli runs list --limit 10 --db "$HB_DB_PATH" 2>/dev/null || true
if [ -d "$HB_REPORTS_DIR" ]; then
  LAST_REPORT=$(ls -t "$HB_REPORTS_DIR"/*/drift_report.json 2>/dev/null | head -1)
  if [ -n "$LAST_REPORT" ] && [ -f "$LAST_REPORT" ]; then
    echo ""
    echo "Last report: $LAST_REPORT"
    python -c "
import json, sys
with open('$LAST_REPORT') as f:
    d = json.load(f)
print('Status:', d.get('status'))
print('Baseline:', d.get('baseline_run_id'))
" 2>/dev/null || true
  fi
fi

# 4) Pilot report (template filled)
REPORT_PATH="$OUT_DIR/pilot_report.md"
cat > "$REPORT_PATH" << EOF
# Pilot Report

**Date:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Out dir:** $OUT_DIR
**DB:** $HB_DB_PATH

## Data sources

- Baseline: $BASELINE_CSV
- Current: $CURRENT_CSV

## Runs

$(python -m hb.cli runs list --limit 20 --db "$HB_DB_PATH" 2>/dev/null || echo "(no runs)")

## Conclusion

Pilot run completed. Review reports in $HB_REPORTS_DIR and evidence packs as needed.
EOF
echo ""
echo "Pilot report: $REPORT_PATH"
echo "Done."
