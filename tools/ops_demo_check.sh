#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-samples/cases/no_drift_pass/current_source.csv}"
RUN_META="${2:-samples/cases/no_drift_pass/current_run_meta.json}"
OUT_DIR="${3:-runs/ops_demo_run}"
REPORTS_DIR="${4:-mvp/reports}"
BASELINE_POLICY="${5:-baseline_policy.yaml}"

if [[ ! -f "$SOURCE" ]]; then
  echo "missing source file: $SOURCE" >&2
  exit 2
fi

if [[ ! -f "$RUN_META" ]]; then
  echo "missing run_meta file: $RUN_META" >&2
  exit 2
fi

bin/hb ingest --source pba_excel "$SOURCE" --run-meta "$RUN_META" --out "$OUT_DIR" >/dev/null
bin/hb analyze --run "$OUT_DIR" --baseline-policy "$BASELINE_POLICY" --reports "$REPORTS_DIR" >/dev/null

RUN_ID=$(jq -r '.run_id' "$OUT_DIR/run_meta_normalized.json")
REPORT_JSON="$REPORTS_DIR/$RUN_ID/drift_report.json"

if [[ ! -f "$REPORT_JSON" ]]; then
  echo "missing report: $REPORT_JSON" >&2
  exit 2
fi

STATUS=$(jq -r '.status' "$REPORT_JSON")
if [[ "$STATUS" != "PASS" ]]; then
  echo "demo run alert: status=$STATUS (expected PASS)" >&2
  exit 1
fi

echo "ok: demo run PASS ($RUN_ID)"
