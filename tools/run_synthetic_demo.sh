#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SYN_DIR="${ROOT_DIR}/samples/synthetic"
HB="${ROOT_DIR}/bin/hb"

if [ ! -d "${SYN_DIR}" ]; then
  echo "synthetic runs not found: ${SYN_DIR}"
  echo "run: python tools/make_synthetic_runs.py --baseline-count 5 --drift-count 5 --out samples/synthetic"
  exit 1
fi

echo "Running baseline runs..."
for run_dir in "${SYN_DIR}"/baseline_*; do
  if [ -d "${run_dir}" ]; then
    echo "  ${run_dir}"
    "${HB}" run --source pba_excel "${run_dir}/source.csv" --run-meta "${run_dir}/run_meta.json"
    python - "${run_dir}" <<'PY'
import json, os, sys
run_dir = sys.argv[1]
meta_path = os.path.join(run_dir, "run_meta.json")
with open(meta_path, "r") as f:
    run_id = json.load(f)["run_id"]
report_path = os.path.join("mvp", "reports", run_id, "drift_report.json")
with open(report_path, "r") as f:
    report = json.load(f)
top = report.get("top_drifts", [])
summary = " ".join(f"{d['metric']} delta={d['delta']}" for d in top[:3])
print(f"    {run_id} {report['status']} baseline={report.get('baseline_run_id')} {summary}")
PY
  fi
done

echo "Running drifted runs..."
for run_dir in "${SYN_DIR}"/drift_*; do
  if [ -d "${run_dir}" ]; then
    echo "  ${run_dir}"
    "${HB}" run --source pba_excel "${run_dir}/source.csv" --run-meta "${run_dir}/run_meta.json"
    python - "${run_dir}" <<'PY'
import json, os, sys
run_dir = sys.argv[1]
meta_path = os.path.join(run_dir, "run_meta.json")
with open(meta_path, "r") as f:
    run_id = json.load(f)["run_id"]
report_path = os.path.join("mvp", "reports", run_id, "drift_report.json")
with open(report_path, "r") as f:
    report = json.load(f)
top = report.get("top_drifts", [])
summary = " ".join(f"{d['metric']} delta={d['delta']}" for d in top[:3])
print(f"    {run_id} {report['status']} baseline={report.get('baseline_run_id')} {summary}")
PY
  fi
done
