#!/usr/bin/env sh
set -eu

# Two-run demo walkthrough (baseline vs current)

BASELINE_FILE="mvp/runs/baseline/baseline-run.csv"
CURRENT_FILE="mvp/runs/current/current-run.csv"
CONFIG_FILE="mvp/config/thresholds.yaml"
OUT_DIR="mvp/reports/current"

echo "1) Analyze baseline:"
echo "   analyze --run ${BASELINE_FILE} --baseline ${BASELINE_FILE} --config ${CONFIG_FILE} --out mvp/reports/baseline"
echo "   ./sentinel analyze ${BASELINE_FILE} --source basic_csv --baseline ${BASELINE_FILE}"
echo "   ./sentinel baseline set <run-id> --tag golden"

echo "2) Analyze current vs baseline:"
echo "   analyze --run ${CURRENT_FILE} --baseline ${BASELINE_FILE} --config ${CONFIG_FILE} --out ${OUT_DIR}"
echo "   ./sentinel analyze ${CURRENT_FILE} --source basic_csv --baseline golden"

echo "3) Expected output:"
echo "   - mvp/reports/current/run-summary.txt -> PASS-with-drift"
echo "   - mvp/reports/current/run-report.html"
echo "   - mvp/reports/current/run-diff.json"
echo "   - mvp/registry/runs.db (run registry)"
