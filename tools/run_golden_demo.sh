#!/usr/bin/env sh
# Golden Demo: one perfect demo story for sales/ops.
# Scenario 1: Baseline run (clean) -> PASS.
# Scenario 2: Second run (PASS but subtle drift) -> PASS_WITH_DRIFT.
# Scenario 3: Third run (FAIL) -> HB flags drift, escalates, evidence pack, trust dashboard.
# Usage: ./tools/run_golden_demo.sh [--out-dir /path]

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

OUT_DIR="${OUT_DIR:-$REPO_ROOT/golden_demo_output}"
while [ $# -gt 0 ]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift ;;
    *) ;;
  esac
  shift
done

mkdir -p "$OUT_DIR"
export HB_DB_PATH="$OUT_DIR/runs.db"
export HB_REPORTS_DIR="$OUT_DIR/reports"
SAMPLES="$REPO_ROOT/samples/cases"

echo "=== Golden Demo: baseline (clean) -> pass+drift -> FAIL ==="
echo "OUT_DIR=$OUT_DIR"

# 1) Baseline run (clean) -> PASS
echo ""
echo "[1/3] Baseline run (no_drift_pass)..."
python -m hb.cli run --source pba_excel "$SAMPLES/no_drift_pass/current_source.csv" \
  --run-meta "$SAMPLES/no_drift_pass/current_run_meta.json" \
  --db "$HB_DB_PATH" --reports "$HB_REPORTS_DIR" 2>/dev/null || true
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

# 2) Second run (subtle drift) -> PASS_WITH_DRIFT
echo ""
echo "[2/3] Second run (single_metric_drift)..."
python -m hb.cli run --source pba_excel "$SAMPLES/single_metric_drift/current_source.csv" \
  --run-meta "$SAMPLES/single_metric_drift/current_run_meta.json" \
  --db "$HB_DB_PATH" --reports "$HB_REPORTS_DIR" 2>/dev/null || true

# 3) Third run (FAIL)
echo ""
echo "[3/3] Third run (reset_triggered_fail)..."
python -m hb.cli run --source pba_excel "$SAMPLES/reset_triggered_fail/current_source.csv" \
  --run-meta "$SAMPLES/reset_triggered_fail/current_run_meta.json" \
  --db "$HB_DB_PATH" --reports "$HB_REPORTS_DIR" 2>/dev/null || true

# Summary: list runs and last report statuses
echo ""
echo "=== Demo runs ==="
python -m hb.cli runs list --limit 5 --db "$HB_DB_PATH" 2>/dev/null || true

echo ""
echo "=== Last report (third run) ==="
LAST_REPORT=$(ls -t "$HB_REPORTS_DIR"/*/drift_report.json 2>/dev/null | head -1)
if [ -n "$LAST_REPORT" ] && [ -f "$LAST_REPORT" ]; then
  python -c "
import json
with open('$LAST_REPORT') as f:
  d = json.load(f)
print('Status:', d.get('status'))
print('Baseline:', d.get('baseline_run_id'))
print('Decision confidence:', d.get('decision_confidence', 'N/A'))
"
fi

echo ""
echo "=== HB Trust Metrics (if feedback present) ==="
python -m hb.cli trust 2>/dev/null || echo "Run 'hb trust' after recording feedback for accuracy."

echo ""
echo "=== Golden Demo complete ==="
echo "Reports: $HB_REPORTS_DIR"
echo "Evidence packs: export with 'hb export evidence-pack --case <run_id> --report-dir <report_dir> --out $OUT_DIR/evidence_packs --zip'"
