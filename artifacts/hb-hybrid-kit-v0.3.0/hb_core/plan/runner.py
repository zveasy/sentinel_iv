import json
import os
import time
import uuid

import yaml

from hb import engine
from hb.config import load_baseline_policy, load_compare_plan, load_metric_registry
from hb.report import write_report
from hb_core.artifact import load_metrics_csv, load_run_meta, validate_artifact_dir
from hb_core.asserts import evaluate_asserts, load_asserts
from hb_core.trend import build_trend, read_plan_history
from hb.redaction import apply_redaction


def _metrics_map(rows):
    metrics = {}
    for row in rows:
        metric = row.get("metric")
        if not metric:
            continue
        value = row.get("value")
        if value == "" or value is None:
            metrics[metric] = None
            continue
        try:
            metrics[metric] = float(value)
        except ValueError:
            metrics[metric] = None
    return metrics


def _metrics_struct(rows):
    metrics = {}
    for row in rows:
        metric = row.get("metric")
        if not metric:
            continue
        value = row.get("value")
        metrics[metric] = {
            "value": float(value) if value not in ("", None) else None,
            "unit": row.get("unit") or None,
            "tags": row.get("tags") or None,
        }
    return metrics


def _merge_status(drift_status, assert_results):
    has_fail = any(item.get("status") == "FAIL" for item in assert_results)
    has_no_test = any(item.get("status") == "NO_TEST" for item in assert_results)
    if has_fail:
        return "FAIL"
    if drift_status == "PASS_WITH_DRIFT":
        return "PASS_WITH_DRIFT"
    if drift_status == "FAIL":
        return "FAIL"
    if has_no_test and drift_status == "PASS":
        return "NO_TEST"
    return "PASS"


def _write_trace_matrix(trace_rows, out_dir):
    json_path = os.path.join(out_dir, "trace_matrix.json")
    csv_path = os.path.join(out_dir, "trace_matrix.csv")
    with open(json_path, "w") as f:
        json.dump(trace_rows, f, indent=2)
    with open(csv_path, "w") as f:
        f.write("requirement_id,scenario_id,status\n")
        for row in trace_rows:
            f.write(f"{row['requirement_id']},{row['scenario_id']},{row['status']}\n")
    return json_path, csv_path


def _load_baseline_store(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _save_baseline_store(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def run_plan(plan_path, out_dir, metric_registry, baseline_policy, asserts_dir=None):
    with open(plan_path, "r") as f:
        plan = yaml.safe_load(f) or {}

    requirements = plan.get("requirements", [])
    scenarios = plan.get("scenarios", [])
    plan_id = plan.get("plan_id") or os.path.basename(plan_path).split(".")[0]
    plan_dir = os.path.dirname(os.path.abspath(plan_path))
    redaction_policy = plan.get("redaction_policy")
    if redaction_policy and not os.path.isabs(redaction_policy):
        redaction_policy = os.path.join(plan_dir, redaction_policy)

    os.makedirs(out_dir, exist_ok=True)
    registry = load_metric_registry(metric_registry)
    compare_plan = load_compare_plan(metric_registry)
    policy = load_baseline_policy(baseline_policy)
    distribution_enabled = policy.get("distribution_drift_enabled", True)
    deterministic = os.environ.get("HB_DETERMINISTIC", "0") == "1"
    early_exit = os.environ.get("HB_EARLY_EXIT", "0") == "1"

    scenario_results = []
    trace_rows = []
    history_path = os.path.join(out_dir, "plan_history.jsonl")
    baseline_store_path = os.path.join(out_dir, "baselines.json")
    baseline_store = _load_baseline_store(baseline_store_path)

    for scenario in scenarios:
        scenario_id = scenario.get("id") or f"scenario_{uuid.uuid4().hex[:6]}"
        baseline_mode = (scenario.get("baseline_mode") or "explicit").lower()
        baseline_key = scenario.get("baseline_key") or scenario_id
        baseline_dir = scenario.get("baseline_artifact_dir")
        run_dir = scenario.get("run_artifact_dir")
        if not baseline_dir or not run_dir:
            if baseline_mode != "explicit" and not baseline_dir:
                baseline_dir = baseline_store.get(baseline_key)
            if not baseline_dir or not run_dir:
                raise ValueError(
                    f"scenario {scenario_id} missing baseline_artifact_dir/run_artifact_dir"
                )
        if not os.path.isabs(baseline_dir):
            baseline_dir = os.path.join(plan_dir, baseline_dir)
        if not os.path.isabs(run_dir):
            run_dir = os.path.join(plan_dir, run_dir)

        validate_artifact_dir(baseline_dir)
        validate_artifact_dir(run_dir)

        baseline_meta = load_run_meta(baseline_dir)
        run_meta = load_run_meta(run_dir)
        if redaction_policy:
            baseline_meta = apply_redaction(redaction_policy, baseline_meta)
            run_meta = apply_redaction(redaction_policy, run_meta)
        baseline_rows = load_metrics_csv(baseline_dir)
        run_rows = load_metrics_csv(run_dir)

        metrics_baseline = _metrics_struct(baseline_rows)
        metrics_current = _metrics_struct(run_rows)

        (
            drift_status,
            drift_metrics,
            warnings,
            fail_metrics,
            invariant_violations,
            distribution_drifts,
            drift_attribution,
        ) = engine.compare_metrics(
            metrics_current,
            metrics_baseline,
            registry,
            distribution_enabled=distribution_enabled,
            plan=compare_plan,
            early_exit=early_exit,
            deterministic=deterministic,
        )

        asserts_path = scenario.get("asserts")
        if asserts_path and not os.path.isabs(asserts_path):
            base_dir = asserts_dir or plan_dir
            asserts_path = os.path.join(base_dir, asserts_path)
        assert_results = []
        if asserts_path:
            assert_results = evaluate_asserts(load_asserts(asserts_path), _metrics_map(run_rows))

        status = _merge_status(drift_status, assert_results)

        report_payload = {
            "run_id": run_meta.get("run_id") or f"{scenario_id}_{uuid.uuid4().hex[:6]}",
            "status": status,
            "baseline_run_id": baseline_meta.get("run_id"),
            "hb_version": os.environ.get("HB_VERSION", "dev"),
            "source_type": run_meta.get("toolchain", {}).get("source_system"),
            "baseline_reason": "plan_baseline",
            "baseline_warning": None,
            "baseline_match_level": "plan",
            "baseline_match_fields": [],
            "baseline_match_score": None,
            "baseline_match_possible": None,
            "context_mismatch_expected": False,
            "drift_metrics": drift_metrics,
            "top_drifts": drift_metrics[:5],
            "distribution_drifts": distribution_drifts,
            "drift_attribution": {"top_drivers": drift_attribution},
            "warnings": warnings,
            "fail_metrics": fail_metrics,
            "invariant_violations": invariant_violations,
            "assert_results": assert_results,
        }

        scenario_dir = os.path.join(out_dir, "results", scenario_id)
        json_path, html_path = write_report(scenario_dir, report_payload)

        scenario_results.append(
            {
                "scenario_id": scenario_id,
                "status": status,
                "report_json": json_path,
                "report_html": html_path,
                "asserts": assert_results,
                "run_meta": run_meta,
                "baseline_meta": baseline_meta,
            }
        )
        if status == "PASS" and baseline_mode in ("last_known_good", "rolling"):
            baseline_store[baseline_key] = run_dir
        if scenario.get("set_golden"):
            baseline_store[f"golden:{baseline_key}"] = baseline_dir

        for req in requirements:
            req_id = req.get("id")
            if not req_id:
                continue
            if scenario_id in (req.get("scenarios") or []):
                trace_rows.append(
                    {"requirement_id": req_id, "scenario_id": scenario_id, "status": status}
                )

        with open(history_path, "a") as f:
            entry = {
                "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "plan_id": plan_id,
                "scenario_id": scenario_id,
                "status": status,
                "drift_score": (drift_attribution[0].get("drift_score") if drift_attribution else None),
            }
            f.write(json.dumps(entry) + "\n")

    trace_json, trace_csv = _write_trace_matrix(trace_rows, out_dir)
    _save_baseline_store(baseline_store_path, baseline_store)
    history_rows = read_plan_history(history_path, limit=200)
    trend = {}
    for scenario in scenario_results:
        trend[scenario["scenario_id"]] = build_trend(history_rows, scenario["scenario_id"])
    trend_path = os.path.join(out_dir, "trend.json")
    with open(trend_path, "w") as f:
        json.dump(trend, f, indent=2)
    result_path = os.path.join(out_dir, "plan_result.json")
    payload = {
        "plan_id": plan_id,
        "scenarios": scenario_results,
        "trace_matrix_json": trace_json,
        "trace_matrix_csv": trace_csv,
        "trend_json": trend_path,
    }
    with open(result_path, "w") as f:
        json.dump(payload, f, indent=2)

    report_path = os.path.join(out_dir, "plan_report.html")
    rows = []
    for item in scenario_results:
        rows.append(
            f"<tr><td>{item['scenario_id']}</td>"
            f"<td>{item['status']}</td>"
            f"<td><a href='{os.path.relpath(item['report_html'], out_dir)}'>report</a></td></tr>"
        )
    table = "\n".join(rows)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Plan Report: {plan_id}</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f6f6f6; }}
  </style>
</head>
<body>
  <h1>Plan Report: {plan_id}</h1>
  <p>Trace matrix: <a href="{os.path.relpath(trace_csv, out_dir)}">CSV</a> | <a href="{os.path.relpath(trace_json, out_dir)}">JSON</a></p>
  <p>Trend: <a href="{os.path.relpath(trend_path, out_dir)}">trend.json</a></p>
  <table>
    <thead><tr><th>Scenario</th><th>Status</th><th>Report</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</body>
</html>
"""
    with open(report_path, "w") as f:
        f.write(html)
    payload["plan_report_html"] = report_path

    return payload
