"""
Defensible replay: same input slice + config/registry version -> run compare, diff output.
hb replay --input-slice <metrics.csv or run_dir> --baseline <metrics.csv or run_id> --metric-registry <path> --out <dir>
"""
import hashlib
import json
import os
from typing import Any

from hb.config import load_metric_registry, load_baseline_policy
from hb.engine import compare_metrics
from hb.registry import init_db, fetch_metrics
from hb.report import write_report
from hb.io import read_json


def _load_metrics_from_path(path: str) -> dict[str, Any]:
    if os.path.isdir(path):
        csv_path = os.path.join(path, "metrics_normalized.csv")
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"no metrics_normalized.csv in {path}")
        path = csv_path
    if not path.endswith(".csv") and not path.endswith(".json"):
        path = path + ".csv" if os.path.isfile(path + ".csv") else path + ".json"
    if path.endswith(".json"):
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            return {r["metric"]: {"value": r.get("value"), "unit": r.get("unit", ""), "tags": r.get("tags")} for r in data if r.get("metric")}
        return {k: {"value": v.get("value"), "unit": v.get("unit", ""), "tags": v.get("tags")} for k, v in data.items()}
    metrics = {}
    with open(path, newline="") as f:
        import csv
        for row in csv.DictReader(f):
            m = row.get("metric")
            if not m:
                continue
            try:
                v = float(row.get("value"))
            except (TypeError, ValueError):
                v = None
            metrics[m] = {"value": v, "unit": row.get("unit", ""), "tags": row.get("tags", "")}
    return metrics


def replay_decision(
    input_slice_path: str,
    baseline_path_or_run_id: str,
    metric_registry_path: str,
    baseline_policy_path: str | None = None,
    db_path: str | None = None,
    out_dir: str | None = None,
) -> dict[str, Any]:
    """
    Replay a decision: load slice + baseline, load registry, compare, write report.
    baseline_path_or_run_id: path to metrics CSV/dir or run_id (if db_path given).
    Returns summary dict with status, config_ref (hashes), decision_payload.
    """
    current = _load_metrics_from_path(input_slice_path)
    if db_path and os.path.isfile(db_path):
        conn = init_db(db_path)
        baseline_metrics = fetch_metrics(conn, baseline_path_or_run_id)
        conn.close()
        if not baseline_metrics:
            baseline_metrics = _load_metrics_from_path(baseline_path_or_run_id)
    else:
        baseline_metrics = _load_metrics_from_path(baseline_path_or_run_id)
    registry = load_metric_registry(metric_registry_path)
    policy = load_baseline_policy(baseline_policy_path) if baseline_policy_path and os.path.isfile(baseline_policy_path) else {}
    status, drift_metrics, warnings, fail_metrics, invariant_violations, distribution_drifts, attribution = compare_metrics(
        current, baseline_metrics, registry, distribution_enabled=policy.get("distribution_drift_enabled", True), plan=None, early_exit=False, deterministic=True
    )
    config_ref = {}
    if os.path.isfile(metric_registry_path):
        with open(metric_registry_path, "rb") as f:
            config_ref["metric_registry_sha256"] = hashlib.sha256(f.read()).hexdigest()
    if baseline_policy_path and os.path.isfile(baseline_policy_path):
        with open(baseline_policy_path, "rb") as f:
            config_ref["baseline_policy_sha256"] = hashlib.sha256(f.read()).hexdigest()
    report_payload = {
        "run_id": "replay",
        "correlation_id": os.environ.get("HB_CORRELATION_ID"),
        "status": status,
        "baseline_run_id": baseline_path_or_run_id if not os.path.isfile(baseline_path_or_run_id) else None,
        "drift_metrics": drift_metrics,
        "top_drifts": (drift_metrics or [])[:10],
        "fail_metrics": fail_metrics or [],
        "invariant_violations": invariant_violations or [],
        "warnings": warnings or [],
    }
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        write_report(out_dir, report_payload)
        with open(os.path.join(out_dir, "replay_config_ref.json"), "w") as f:
            json.dump(config_ref, f, indent=2)
    return {"status": status, "config_ref": config_ref, "decision_payload": report_payload}
