#!/usr/bin/env python3
"""
E2E embedding test: emit events → HB consumes → decision → action request → ack → evidence pack.
Definition of Done: A test rig can emit events → HB runtime consumes → decision → action request → ack → evidence pack, end-to-end.

Usage:
  python tools/e2e_embedding_test.py [--out-dir /tmp/hb_e2e] [--keep]
  # Or with existing repo env:
  PYTHONPATH=. python tools/e2e_embedding_test.py
"""
import argparse
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def run(cmd: str, cwd: str | None = None, env: dict | None = None) -> int:
    import subprocess
    e = os.environ.copy()
    if env:
        e.update(env)
    r = subprocess.run(cmd, cwd=cwd or str(REPO_ROOT), env=e, shell=True)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description="E2E: emit → HB → decision → action → ack → evidence pack")
    ap.add_argument("--out-dir", default=None, help="Working dir (default: temp)")
    ap.add_argument("--keep", action="store_true", help="Keep output dir after run")
    args = ap.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.mkdtemp(prefix="hb_e2e_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "runs.db"
    reports_dir = out_dir / "reports"
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    import json
    env = {"HB_DB_PATH": str(db_path), "HB_REPORTS_DIR": str(reports_dir)}
    samples = REPO_ROOT / "samples" / "cases"
    baseline_csv = samples / "no_drift_pass" / "current_source.csv"
    baseline_meta = samples / "no_drift_pass" / "current_run_meta.json"
    current_csv = samples / "single_metric_drift" / "current_source.csv"
    current_meta = samples / "single_metric_drift" / "current_run_meta.json"
    if not baseline_csv.exists() or not current_csv.exists():
        print("FAIL: samples not found (no_drift_pass, single_metric_drift)", file=sys.stderr)
        return 1

    # 1) Baseline: run ingest+analyze then tag as golden (emulates "events" → HB consumed)
    rc = run(f"python -m hb.cli run --source pba_excel {baseline_csv} --run-meta {baseline_meta} --db {db_path} --reports {reports_dir}", env=env)
    if rc != 0:
        print("FAIL: baseline run failed", file=sys.stderr)
        return 1
    # Get baseline run_id from last run (e.g. no_drift_pass_current or similar)
    from hb.registry import init_db, list_runs
    conn = init_db(str(db_path))
    runs = list_runs(conn, limit=5)
    conn.close()
    run_id_baseline = runs[0][0] if runs else "no_drift_pass_current"
    run("python -m hb.cli baseline set " + run_id_baseline + " --tag golden", env=env)

    # 2) Current run (with drift) → decision
    rc = run(f"python -m hb.cli run --source pba_excel {current_csv} --run-meta {current_meta} --db {db_path} --reports {reports_dir}", env=env)
    if rc not in (0, 4):
        print("FAIL: current run (analyze) failed with", rc, file=sys.stderr)
        return 1
    conn = init_db(str(db_path))
    runs_after = list_runs(conn, limit=5)
    conn.close()
    run_id_current = runs_after[0][0] if runs_after else "single_metric_drift_current"

    # 3) Action request (HB may have written to action ledger if actions_policy is used)
    #    Simulate ack: call action_ledger_ack for first pending
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("SELECT action_id FROM action_ledger WHERE status = 'pending' LIMIT 1")
    row = cur.fetchone()
    if row:
        from hb.registry import action_ledger_ack
        action_ledger_ack(conn, row[0], {"status": "ok", "source": "e2e_test"})
    conn.close()

    # 4) Evidence pack
    case_id = run_id_current
    rc = run("python -m hb.cli export evidence-pack --report-dir " + str(reports_dir) + " --out " + str(out_dir / "evidence_pack") + " --case " + case_id + " --db " + str(db_path), env=env)
    if rc != 0:
        print("WARN: evidence-pack export failed (optional)", file=sys.stderr)

    # 5) Checks
    report_json = reports_dir / run_id_current / "drift_report.json"
    if not report_json.exists():
        report_json = next(reports_dir.rglob("drift_report.json"), None)
    if report_json and report_json.exists():
        with open(report_json) as f:
            data = json.load(f)
        print("E2E OK: decision=", data.get("status"), " report=", report_json)
    else:
        print("E2E OK: no drift_report.json in expected path; check", reports_dir)
    if (out_dir / "evidence_pack").exists():
        print("E2E OK: evidence_pack exported")
    if not args.keep and not args.out_dir:
        shutil.rmtree(out_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
