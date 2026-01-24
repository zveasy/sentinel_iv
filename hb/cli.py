import argparse
import hashlib
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import yaml

from hb import engine
from hb import feedback
from hb import local_ui
from hb import watch
from hb_core.compare import run_compare
from hb_core.adapters import VxWorksLogAdapter
from hb.config import load_baseline_policy, load_compare_plan, load_metric_registry
from hb.perf import PerfRecorder
from hb_core.plan import run_plan
from hb.adapters import (
    cmapss_fd001,
    cmapss_fd002,
    cmapss_fd003,
    cmapss_fd004,
    custom_tabular,
    nasa_http_tsv,
    pba_excel_adapter,
    smap_msl_adapter,
)
from hb.io import read_json, write_json, write_metrics_csv
from hb.registry import (
    init_db,
    upsert_run,
    replace_metrics,
    fetch_metrics,
    select_baseline,
    set_baseline_tag,
    list_baseline_tags,
    list_runs,
    add_baseline_approval,
    list_baseline_approvals,
    add_baseline_request,
    list_baseline_requests,
    get_baseline_request,
    set_baseline_request_status,
    count_baseline_approvals,
    run_exists,
)
from hb.registry_utils import build_alias_index
from hb.audit import append_audit_log, write_artifact_manifest, verify_artifact_manifest
from hb.report import write_report, write_pdf
from hb.security import load_key, sign_file, verify_signature, encrypt_file
from hb.redaction import apply_redaction


def file_hash(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:12]


class HBError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


EXIT_OK = 0
EXIT_UNKNOWN = 1
EXIT_PARSE = 2
EXIT_CONFIG = 3
EXIT_REGISTRY = 4

PLAN_EXIT_PASS_WITH_DRIFT = 1
PLAN_EXIT_FAIL = 2
PLAN_EXIT_NO_TEST = 3




def generate_run_id(run_meta):
    if run_meta.get("run_id"):
        return run_meta["run_id"]
    return str(uuid.uuid4())


def normalize_run_meta(run_meta, source_system):
    run_meta.setdefault("run_id", generate_run_id(run_meta))
    run_meta.setdefault("toolchain", {})
    run_meta["toolchain"]["source_system"] = source_system
    run_meta.setdefault("build", {"git_sha": "", "build_id": ""})
    run_meta.setdefault("timestamps", {"start_utc": "", "end_utc": ""})
    return run_meta


def ingest(args):
    adapter_map = {
        "pba_excel": pba_excel_adapter,
        "cmapss_fd001": cmapss_fd001,
        "cmapss_fd002": cmapss_fd002,
        "cmapss_fd003": cmapss_fd003,
        "cmapss_fd004": cmapss_fd004,
        "nasa_http_tsv": nasa_http_tsv,
        "smap_msl": smap_msl_adapter,
        "custom_tabular": custom_tabular,
    }
    if args.source not in adapter_map:
        raise HBError(f"unknown source adapter: {args.source}", EXIT_CONFIG)

    perf = getattr(args, "perf", None)
    run_meta = read_json(args.run_meta) if args.run_meta else {}
    run_meta = normalize_run_meta(run_meta, args.source)
    run_id = run_meta["run_id"]

    adapter = adapter_map[args.source]
    use_stream = getattr(args, "stream", False) or os.environ.get("HB_STREAM_INGEST") == "1"
    if perf is None:
        if use_stream and hasattr(adapter, "parse_stream"):
            metrics_raw = adapter.parse_stream(args.path)
        else:
            metrics_raw = adapter.parse(args.path)
    else:
        with perf.span("ingest_run"):
            if use_stream and hasattr(adapter, "parse_stream"):
                metrics_raw = adapter.parse_stream(args.path)
            else:
                metrics_raw = adapter.parse(args.path)
    registry = load_metric_registry(args.metric_registry)
    compare_plan = load_compare_plan(args.metric_registry)
    deterministic = os.environ.get("HB_DETERMINISTIC", "0") == "1"
    early_exit = os.environ.get("HB_EARLY_EXIT", "0") == "1"
    metrics_normalized, warnings = engine.normalize_metrics(metrics_raw, registry)

    out_dir = args.out or os.path.join("runs", run_id)
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "run_meta_normalized.json"), run_meta)

    metrics_rows = []
    for metric in sorted(metrics_normalized.keys()):
        data = metrics_normalized[metric]
        metrics_rows.append(
            {
                "metric": metric,
                "value": data["value"],
                "unit": data.get("unit") or "",
                "tags": data.get("tags") or "",
            }
        )
    write_metrics_csv(os.path.join(out_dir, "metrics_normalized.csv"), metrics_rows)

    if warnings:
        write_json(os.path.join(out_dir, "ingest_warnings.json"), {"warnings": warnings})

    print(f"ingest output: {out_dir}")
    if perf is not None:
        file_ext = os.path.splitext(args.path)[1].lower()
        row_count = None
        if file_ext in {".csv", ".tsv"}:
            try:
                with open(args.path, "r", errors="replace") as f:
                    row_count = max(sum(1 for _ in f) - 1, 0)
            except OSError:
                row_count = None
        perf.add_meta(
            ingest_source=args.path,
            ingest_bytes=os.path.getsize(args.path) if os.path.exists(args.path) else None,
            ingest_metrics=len(metrics_normalized),
            ingest_rows=row_count,
            ingest_file_type=file_ext.lstrip("."),
        )
    return out_dir


def analyze(args):
    run_dir = args.run
    perf = getattr(args, "perf", None)
    if perf is None:
        perf = PerfRecorder()
    run_meta = read_json(os.path.join(run_dir, "run_meta_normalized.json"))
    registry = load_metric_registry(args.metric_registry)
    with perf.span("compile_plan"):
        compare_plan = load_compare_plan(args.metric_registry)
    policy = load_baseline_policy(args.baseline_policy)
    registry_hash = file_hash(args.metric_registry)
    redaction_policy = args.redaction_policy
    distribution_enabled = policy.get("distribution_drift_enabled", True)
    deterministic = os.environ.get("HB_DETERMINISTIC", "0") == "1"
    early_exit = os.environ.get("HB_EARLY_EXIT", "0") == "1"

    conn = init_db(args.db)
    baseline_run_id, baseline_reason, baseline_warning, baseline_match = select_baseline(
        conn, run_meta, policy, registry_hash=registry_hash
    )
    if baseline_run_id:
        baseline_metrics = fetch_metrics(conn, baseline_run_id)
    else:
        baseline_metrics = {}

    metrics_path = os.path.join(run_dir, "metrics_normalized.csv")
    metrics_current = {}
    for row in _read_metrics_csv(metrics_path):
        metrics_current[row["metric"]] = {
            "value": float(row["value"]) if row["value"] != "" else None,
            "unit": row.get("unit") or None,
            "tags": row.get("tags") or None,
        }

    with perf.span("compare_core"):
        (
            status,
            drift_metrics,
            warnings,
            fail_metrics,
            invariant_violations,
            distribution_drifts,
            drift_attribution,
        ) = engine.compare_metrics(
            metrics_current,
            baseline_metrics,
            registry,
            distribution_enabled=distribution_enabled,
            plan=compare_plan,
            early_exit=early_exit,
            deterministic=deterministic,
        )
    context_mismatch_expected = bool(
        baseline_warning and str(baseline_warning).startswith("context mismatch")
    )

    report_meta = run_meta
    if redaction_policy:
        import copy

        report_meta = apply_redaction(
            policy_path=redaction_policy, run_meta=copy.deepcopy(run_meta)
        )

    decision_basis = None
    if drift_attribution:
        top_driver = drift_attribution[0]
        decision_basis = {
            "drift_score": top_driver.get("drift_score"),
            "warn_threshold": top_driver.get("warn_threshold"),
            "fail_threshold": top_driver.get("fail_threshold"),
            "persistence_cycles": top_driver.get("persistence_cycles"),
            "score_type": top_driver.get("score_type"),
        }

    likely_areas = []
    driver_metrics = [item.get("metric_name", "") for item in drift_attribution]
    for metric_name in driver_metrics:
        name = (metric_name or "").lower()
        if "latency" in name or "lag" in name:
            likely_areas.extend(
                [
                    "runtime scheduling",
                    "request queuing",
                    "downstream service latency",
                    "resource saturation",
                ]
            )
        if "error" in name or "failure" in name or "reset" in name:
            likely_areas.extend(
                [
                    "transport reliability",
                    "schema validation",
                    "upstream failures",
                    "retries/timeouts",
                ]
            )
        if "throughput" in name or "rate" in name or "qps" in name:
            likely_areas.extend(
                [
                    "backpressure",
                    "rate limits",
                    "queue depth",
                    "ingest contention",
                ]
            )
    likely_areas = sorted({area for area in likely_areas}) if likely_areas else []

    report_payload = {
        "run_id": report_meta["run_id"],
        "status": status,
        "baseline_run_id": baseline_run_id,
        "hb_version": os.environ.get("HB_VERSION", "dev"),
        "source_type": run_meta.get("toolchain", {}).get("source_system"),
        "baseline_reason": baseline_reason,
        "baseline_warning": baseline_warning,
        "baseline_match_level": baseline_match.get("level"),
        "baseline_match_fields": baseline_match.get("matched_fields", []),
        "baseline_match_score": baseline_match.get("score"),
        "baseline_match_possible": baseline_match.get("possible"),
        "context_mismatch_expected": context_mismatch_expected,
        "drift_metrics": drift_metrics,
        "top_drifts": drift_metrics[: args.top],
        "distribution_drifts": distribution_drifts,
        "drift_attribution": {"top_drivers": drift_attribution},
        "likely_investigation_areas": likely_areas,
        "decision_basis": decision_basis,
        "warnings": warnings,
        "fail_metrics": fail_metrics,
        "invariant_violations": invariant_violations,
    }

    report_dir = os.path.join(args.reports, report_meta["run_id"])
    with perf.span("render_report"):
        json_path, html_path = write_report(report_dir, report_payload)
    if getattr(args, "pdf", False):
        pdf_path = os.path.join(report_dir, "drift_report.pdf")
        _, error = write_pdf(html_path, pdf_path)
        if error:
            print(f"pdf export warning: {error}")
    else:
        pdf_path = None

    baseline_line = f"baseline: {baseline_run_id or 'none'} ({baseline_reason})"
    if baseline_match.get("level"):
        baseline_line += f" match={baseline_match.get('level')}"
    print(baseline_line)
    if baseline_warning:
        print(f"baseline warning: {baseline_warning}")

    manifest_path = write_artifact_manifest(
        report_dir,
        [
            json_path,
            html_path,
            pdf_path,
            os.path.join(report_dir, "metrics_normalized.csv"),
            os.path.join(report_dir, "run_meta_normalized.json"),
        ],
    )
    if getattr(args, "sign_key", None):
        key_bytes = load_key(args.sign_key)
        sig = sign_file(manifest_path, key_bytes)
        with open(manifest_path + ".sig", "w") as f:
            f.write(sig + "\n")
    if getattr(args, "encrypt_key", None):
        key_bytes = load_key(args.encrypt_key)
        for path in [json_path, html_path, pdf_path, manifest_path]:
            if path and os.path.exists(path):
                out_path, error = encrypt_file(path, key_bytes)
                if error:
                    print(f"encrypt warning: {error}")
                else:
                    print(f"encrypted: {out_path}")
    append_audit_log(
        report_dir,
        report_meta["run_id"],
        "analyze",
        {
            "status": status,
            "baseline_run_id": baseline_run_id,
            "baseline_reason": baseline_reason,
            "artifact_manifest": os.path.abspath(manifest_path),
        },
    )

    upsert_run(
        conn,
        run_meta,
        status,
        baseline_run_id=baseline_run_id,
        registry_hash=registry_hash,
    )
    replace_metrics(conn, run_meta["run_id"], _metrics_to_rows(metrics_current))

    write_json(os.path.join(report_dir, "run_meta_normalized.json"), report_meta)
    write_metrics_csv(os.path.join(report_dir, "metrics_normalized.csv"), _metrics_to_rows(metrics_current))

    print(f"report output: {report_dir}")
    perf.add_meta(
        metrics_count=len(metrics_current),
        metrics_bytes=os.path.getsize(metrics_path) if os.path.exists(metrics_path) else None,
        baseline_run_id=baseline_run_id,
    )
    perf.write(os.path.join(report_dir, "perf.json"))
    return report_dir


def run(args):
    perf = getattr(args, "perf", None)
    if perf is None:
        perf = PerfRecorder()
    args.perf = perf
    run_dir = ingest(args)
    analyze_args = argparse.Namespace(
        run=run_dir,
        baseline_policy=args.baseline_policy,
        metric_registry=args.metric_registry,
        db=args.db,
        reports=args.reports,
        top=args.top,
        pdf=args.pdf,
        encrypt_key=args.encrypt_key,
        sign_key=args.sign_key,
        redaction_policy=args.redaction_policy,
        perf=perf,
    )
    report_dir = analyze(analyze_args)
    print(f"run output: {report_dir}")
    return report_dir


def feedback_record(args):
    payload = feedback.load_feedback_payload(args.input)
    feedback.write_feedback_record(payload, log_path=args.log)
    print(f"feedback recorded: {args.log or feedback.default_log_path()}")


def feedback_export(args):
    feedback.export_feedback(args.log, args.output, mode=args.mode)
    print(f"feedback export written: {args.output}")


def feedback_serve(args):
    feedback.serve_feedback(port=args.port, log_path=args.log)


def baseline_set(args):
    policy = load_baseline_policy(args.baseline_policy)
    governance = policy.get("governance", {})
    if governance.get("require_approval") and not args.force:
        raise HBError(
            "baseline changes require approval; use baseline request/approve or pass --force",
            EXIT_CONFIG,
        )
    conn = init_db(args.db)
    if not run_exists(conn, args.run_id):
        raise HBError(f"run_id not found: {args.run_id}", EXIT_CONFIG)
    registry_hash = file_hash(args.metric_registry)
    set_baseline_tag(conn, args.tag, args.run_id, registry_hash)
    print(f"baseline tag set: {args.tag} -> {args.run_id}")


def baseline_list(args):
    conn = init_db(args.db)
    rows = list_baseline_tags(conn)
    if not rows:
        print("no baseline tags found")
        return
    print("tag | run_id | registry_hash | created_at")
    print("----+--------+---------------+-----------")
    for row in rows:
        print(" | ".join(str(value) for value in row))


def baseline_approve(args):
    policy = load_baseline_policy(args.baseline_policy)
    governance = policy.get("governance", {})
    allowed_approvers = governance.get("approvers") or []
    approvals_required = int(governance.get("approvals_required", 1))
    conn = init_db(args.db)
    if not run_exists(conn, args.run_id):
        raise HBError(f"run_id not found: {args.run_id}", EXIT_CONFIG)
    if allowed_approvers and args.approved_by not in allowed_approvers:
        raise HBError(f"approver not authorized: {args.approved_by}", EXIT_CONFIG)

    request = get_baseline_request(conn, request_id=args.request_id, run_id=args.run_id, tag=args.tag)
    if governance.get("require_approval") and not request:
        raise HBError("no pending baseline request found", EXIT_CONFIG)

    approval_id = args.approval_id or str(uuid.uuid4())
    add_baseline_approval(
        conn,
        approval_id,
        args.run_id,
        args.tag,
        args.approved_by,
        args.reason or "",
        request_id=request[0] if request else None,
    )
    approval_count = count_baseline_approvals(
        conn, request_id=request[0] if request else None, run_id=args.run_id, tag=args.tag
    )
    if approval_count >= approvals_required or not governance.get("require_approval"):
        set_baseline_tag(conn, args.tag, args.run_id, file_hash(args.metric_registry))
        if request:
            set_baseline_request_status(
                conn, request[0], "approved", approved_at=datetime.now(timezone.utc).isoformat()
            )
        print(f"baseline approved: {args.tag} -> {args.run_id} by {args.approved_by}")
    else:
        print(
            "approval recorded: "
            f"{approval_count}/{approvals_required} required for {args.tag} -> {args.run_id}"
        )


def baseline_approvals(args):
    conn = init_db(args.db)
    rows = list_baseline_approvals(conn, limit=args.limit)
    if not rows:
        print("no baseline approvals found")
        return
    print("approval_id | run_id | tag | approved_by | reason | approved_at | request_id")
    print("------------+--------+-----+-------------+--------+-----------+-----------")
    for row in rows:
        print(" | ".join(str(value) for value in row))


def baseline_request(args):
    conn = init_db(args.db)
    if not run_exists(conn, args.run_id):
        raise HBError(f"run_id not found: {args.run_id}", EXIT_CONFIG)
    request_id = args.request_id or str(uuid.uuid4())
    add_baseline_request(
        conn,
        request_id,
        args.run_id,
        args.tag,
        args.requested_by,
        args.reason or "",
    )
    print(f"baseline request created: {request_id} for {args.tag} -> {args.run_id}")


def baseline_requests(args):
    conn = init_db(args.db)
    rows = list_baseline_requests(conn, limit=args.limit)
    if not rows:
        print("no baseline requests found")
        return
    print("request_id | run_id | tag | requested_by | reason | status | requested_at | approved_at")
    print("----------+--------+-----+--------------+--------+--------+--------------+-----------")
    for row in rows:
        print(" | ".join(str(value) for value in row))


def runs_list(args):
    conn = init_db(args.db)
    rows = list_runs(conn, limit=args.limit)
    if not rows:
        print("no runs found")
        return
    print("run_id | status | program | subsystem | test_name | created_at")
    print("-------+--------+---------+-----------+-----------+-----------")
    for row in rows:
        print(" | ".join(str(value) for value in row))


def verify_report(args):
    manifest_path = os.path.join(args.report_dir, "artifact_manifest.json")
    sig_path = manifest_path + ".sig"
    if not os.path.exists(manifest_path):
        raise HBError("artifact manifest missing", EXIT_CONFIG)
    issues = verify_artifact_manifest(manifest_path)
    if issues:
        raise HBError(f"artifact manifest verification failed: {issues[0]}", EXIT_CONFIG)
    print("artifact manifest OK")

    if args.sign_key:
        if not os.path.exists(sig_path):
            raise HBError("signature missing", EXIT_CONFIG)
        key_bytes = load_key(args.sign_key)
        with open(sig_path, "r") as f:
            expected = f.read().strip()
        ok = verify_signature(manifest_path, key_bytes, expected)
        if ok:
            print("signature OK")
            return
        raise HBError("signature verification failed", EXIT_CONFIG)


def _read_metrics_csv(path):
    import csv

    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def _metrics_to_rows(metrics):
    rows = []
    for metric in sorted(metrics.keys()):
        data = metrics[metric]
        rows.append(
            {
                "metric": metric,
                "value": data["value"],
                "unit": data.get("unit") or "",
                "tags": data.get("tags") or "",
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Harmony Bridge CLI")
    parser.add_argument("--metric-registry", default=os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml"))
    parser.add_argument("--baseline-policy", default=os.environ.get("HB_BASELINE_POLICY", "baseline_policy.yaml"))
    parser.add_argument("--db", default=os.environ.get("HB_DB_PATH", "runs.db"))
    parser.add_argument("--reports", default=os.environ.get("HB_REPORTS_DIR", os.path.join("mvp", "reports")))
    parser.add_argument("--top", type=int, default=5)

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="ingest source artifacts")
    ingest_parser.add_argument("--source", default="pba_excel")
    ingest_parser.add_argument("path")
    ingest_parser.add_argument("--run-meta", default=None)
    ingest_parser.add_argument("--out", default=None)
    ingest_parser.add_argument("--stream", action="store_true")

    analyze_parser = subparsers.add_parser("analyze", help="analyze a run directory")
    analyze_parser.add_argument("--run", required=True)
    analyze_parser.add_argument("--baseline-policy", default=None)
    analyze_parser.add_argument("--metric-registry", default=None)
    analyze_parser.add_argument("--db", default=None)
    analyze_parser.add_argument("--reports", default=None)
    analyze_parser.add_argument("--top", type=int, default=None)
    analyze_parser.add_argument("--pdf", action="store_true")
    analyze_parser.add_argument("--encrypt-key", default=None)
    analyze_parser.add_argument("--sign-key", default=None)
    analyze_parser.add_argument("--redaction-policy", default=None)

    run_parser = subparsers.add_parser("run", help="ingest + analyze")
    run_parser.add_argument("--source", default="pba_excel")
    run_parser.add_argument("path")
    run_parser.add_argument("--run-meta", default=None)
    run_parser.add_argument("--out", default=None)
    run_parser.add_argument("--stream", action="store_true")
    run_parser.add_argument("--baseline-policy", default=None)
    run_parser.add_argument("--metric-registry", default=None)
    run_parser.add_argument("--db", default=None)
    run_parser.add_argument("--reports", default=None)
    run_parser.add_argument("--top", type=int, default=None)
    run_parser.add_argument("--pdf", action="store_true")
    run_parser.add_argument("--encrypt-key", default=None)
    run_parser.add_argument("--sign-key", default=None)
    run_parser.add_argument("--redaction-policy", default=None)

    baseline_parser = subparsers.add_parser("baseline", help="baseline governance")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_cmd", required=True)
    baseline_set_cmd = baseline_sub.add_parser("set", help="set baseline tag")
    baseline_set_cmd.add_argument("run_id")
    baseline_set_cmd.add_argument("--tag", default="golden")
    baseline_set_cmd.add_argument("--force", action="store_true")
    baseline_set_cmd.add_argument("--baseline-policy", default=None)
    baseline_list_cmd = baseline_sub.add_parser("list", help="list baseline tags")
    baseline_set_cmd.add_argument("--metric-registry", default=None)
    baseline_set_cmd.add_argument("--db", default=None)
    baseline_list_cmd.add_argument("--db", default=None)
    baseline_list_cmd.add_argument("--metric-registry", default=None)
    baseline_request_cmd = baseline_sub.add_parser("request", help="request baseline change")
    baseline_request_cmd.add_argument("run_id")
    baseline_request_cmd.add_argument("--tag", default="golden")
    baseline_request_cmd.add_argument("--requested-by", required=True)
    baseline_request_cmd.add_argument("--reason", default="")
    baseline_request_cmd.add_argument("--request-id", default=None)
    baseline_request_cmd.add_argument("--db", default=None)
    baseline_approve_cmd = baseline_sub.add_parser("approve", help="approve baseline change")
    baseline_approve_cmd.add_argument("run_id")
    baseline_approve_cmd.add_argument("--tag", default="golden")
    baseline_approve_cmd.add_argument("--approved-by", required=True)
    baseline_approve_cmd.add_argument("--reason", default="")
    baseline_approve_cmd.add_argument("--approval-id", default=None)
    baseline_approve_cmd.add_argument("--request-id", default=None)
    baseline_approve_cmd.add_argument("--baseline-policy", default=None)
    baseline_approve_cmd.add_argument("--metric-registry", default=None)
    baseline_approve_cmd.add_argument("--db", default=None)
    baseline_approvals_cmd = baseline_sub.add_parser("approvals", help="list baseline approvals")
    baseline_approvals_cmd.add_argument("--limit", type=int, default=50)
    baseline_approvals_cmd.add_argument("--db", default=None)
    baseline_requests_cmd = baseline_sub.add_parser("requests", help="list baseline requests")
    baseline_requests_cmd.add_argument("--limit", type=int, default=50)
    baseline_requests_cmd.add_argument("--db", default=None)

    runs_parser = subparsers.add_parser("runs", help="run registry")
    runs_sub = runs_parser.add_subparsers(dest="runs_cmd", required=True)
    runs_list_cmd = runs_sub.add_parser("list", help="list recent runs")
    runs_list_cmd.add_argument("--limit", type=int, default=20)
    runs_list_cmd.add_argument("--db", default=None)

    verify_parser = subparsers.add_parser("verify", help="verify report signature")
    verify_parser.add_argument("--report-dir", required=True)
    verify_parser.add_argument("--sign-key", required=False)

    ui_parser = subparsers.add_parser("ui", help="run local web UI (localhost only)")
    ui_parser.add_argument("--port", type=int, default=int(os.environ.get("HB_UI_PORT", 8765)))

    compare_parser = subparsers.add_parser("compare", help="compare baseline and run artifacts")
    compare_parser.add_argument("--baseline", required=True, help="path to baseline artifact")
    compare_parser.add_argument("--run", required=True, help="path to run artifact")
    compare_parser.add_argument("--out", required=True, help="output directory")
    compare_parser.add_argument("--schema-mode", choices=["auto", "file", "none"], default="auto")
    compare_parser.add_argument("--schema-path", default=None, help="schema path when using --schema-mode file")
    compare_parser.add_argument("--thresholds-path", default=None, help="thresholds/baseline policy path")
    compare_parser.add_argument("--run-meta", default=None, help="run meta JSON (applies to both)")
    compare_parser.add_argument("--source", default=None, help="override source adapter (e.g., pba_excel)")

    plan_parser = subparsers.add_parser("plan", help="plan runner")
    plan_sub = plan_parser.add_subparsers(dest="plan_cmd", required=True)
    plan_run_cmd = plan_sub.add_parser("run", help="run a plan YAML")
    plan_run_cmd.add_argument("plan_path")
    plan_run_cmd.add_argument("--out", default="plan_output")
    plan_run_cmd.add_argument("--metric-registry", default=None)
    plan_run_cmd.add_argument("--baseline-policy", default=None)
    plan_run_cmd.add_argument("--asserts-dir", default=None)

    bundle_parser = subparsers.add_parser("bundle", help="bundle results into a zip")
    bundle_parser.add_argument("results_dir")
    bundle_parser.add_argument("--out", default=None)

    adapter_parser = subparsers.add_parser("adapter", help="adapter utilities")
    adapter_sub = adapter_parser.add_subparsers(dest="adapter_cmd", required=True)
    vxworks_cmd = adapter_sub.add_parser("vxworks", help="export VxWorks log to artifact_dir")
    vxworks_cmd.add_argument("--log", required=True, help="path to VxWorks log")
    vxworks_cmd.add_argument("--out", required=True, help="output artifact_dir")
    vxworks_cmd.add_argument("--baseline-log", default=None, help="baseline log for profile inference")
    vxworks_cmd.add_argument("--profile", default=None, help="existing parser_profile.json")
    vxworks_cmd.add_argument("--run-meta", default=None, help="run_meta.json override")

    watch_parser = subparsers.add_parser("watch", help="watch a folder and run drift checks")
    watch_parser.add_argument("--dir", required=True, help="directory to watch")
    watch_parser.add_argument("--source", required=True, help="source type")
    watch_parser.add_argument("--pattern", default="*", help="glob pattern for files")
    watch_parser.add_argument("--interval", type=int, default=604800, help="poll interval in seconds")
    watch_parser.add_argument("--workspace", default=None, help="workspace root (default ~/.harmony_bridge)")
    watch_parser.add_argument("--run-meta", default=None, help="run_meta.json to apply to all files")
    watch_parser.add_argument("--run-meta-dir", default=None, help="directory with per-file run_meta.json")
    watch_parser.add_argument("--open-report", action="store_true", help="auto-open reports")
    watch_parser.add_argument("--once", action="store_true", help="process current files then exit")

    feedback_parser = subparsers.add_parser("feedback", help="feedback utilities")
    feedback_sub = feedback_parser.add_subparsers(dest="feedback_cmd", required=True)

    feedback_record_cmd = feedback_sub.add_parser("record", help="record feedback payload")
    feedback_record_cmd.add_argument("--input", required=True, help="path to feedback JSON payload")
    feedback_record_cmd.add_argument("--log", default=None, help="override feedback log path")

    feedback_export_cmd = feedback_sub.add_parser("export", help="export feedback summary or raw records")
    feedback_export_cmd.add_argument("--log", default=None, help="override feedback log path")
    feedback_export_cmd.add_argument("--output", required=True, help="output JSON path")
    feedback_export_cmd.add_argument("--mode", choices=["summary", "raw"], default="summary")

    feedback_serve_cmd = feedback_sub.add_parser("serve", help="run local feedback server")
    feedback_serve_cmd.add_argument("--log", default=None, help="override feedback log path")
    feedback_serve_cmd.add_argument("--port", type=int, default=int(os.environ.get("HB_FEEDBACK_PORT", 8765)))

    db_parser = subparsers.add_parser("db", help="database utilities")
    db_sub = db_parser.add_subparsers(dest="db_cmd", required=True)
    db_encrypt = db_sub.add_parser("encrypt", help="encrypt runs.db with sqlcipher")
    db_encrypt.add_argument("--input", default="runs.db")
    db_encrypt.add_argument("--output", default="runs_encrypted.db")
    db_encrypt.add_argument("--key", required=True)
    db_decrypt = db_sub.add_parser("decrypt", help="decrypt runs.db with sqlcipher")
    db_decrypt.add_argument("--input", default="runs_encrypted.db")
    db_decrypt.add_argument("--output", default="runs.db")
    db_decrypt.add_argument("--key", required=True)

    args = parser.parse_args()

    try:
        if args.command == "ingest":
            ingest(args)
        elif args.command == "analyze":
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            if args.baseline_policy is None:
                args.baseline_policy = parser.get_default("baseline_policy")
            if args.db is None:
                args.db = parser.get_default("db")
            if args.reports is None:
                args.reports = parser.get_default("reports")
            if args.top is None:
                args.top = parser.get_default("top")
            if args.pdf is None:
                args.pdf = False
            if args.encrypt_key is None:
                args.encrypt_key = None
            if args.sign_key is None:
                args.sign_key = None
            analyze(args)
        elif args.command == "run":
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            if args.baseline_policy is None:
                args.baseline_policy = parser.get_default("baseline_policy")
            if args.db is None:
                args.db = parser.get_default("db")
            if args.reports is None:
                args.reports = parser.get_default("reports")
            if args.top is None:
                args.top = parser.get_default("top")
            if args.pdf is None:
                args.pdf = False
            if args.encrypt_key is None:
                args.encrypt_key = None
            if args.sign_key is None:
                args.sign_key = None
            if args.redaction_policy is None:
                args.redaction_policy = None
            run(args)
        elif args.command == "baseline":
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            if args.db is None:
                args.db = parser.get_default("db")
            if getattr(args, "baseline_policy", None) is None:
                args.baseline_policy = parser.get_default("baseline_policy")
            if args.baseline_cmd == "set":
                baseline_set(args)
            elif args.baseline_cmd == "list":
                baseline_list(args)
            elif args.baseline_cmd == "request":
                baseline_request(args)
            elif args.baseline_cmd == "approve":
                baseline_approve(args)
            elif args.baseline_cmd == "approvals":
                baseline_approvals(args)
            elif args.baseline_cmd == "requests":
                baseline_requests(args)
        elif args.command == "runs":
            if args.db is None:
                args.db = parser.get_default("db")
            if args.runs_cmd == "list":
                runs_list(args)
        elif args.command == "verify":
            verify_report(args)
        elif args.command == "ui":
            if os.environ.get("HB_UI_LEGACY") == "1":
                host = os.environ.get("HB_UI_HOST", "127.0.0.1")
                local_ui.serve_local_ui(port=args.port, host=host)
            else:
                try:
                    import importlib.util

                    def _ui_deps_missing():
                        missing = []
                        if importlib.util.find_spec("fastapi") is None:
                            missing.append("fastapi")
                        if importlib.util.find_spec("uvicorn") is None:
                            missing.append("uvicorn")
                        if importlib.util.find_spec("multipart") is None:
                            missing.append("python-multipart")
                        return missing

                    missing = _ui_deps_missing()
                    if missing and os.environ.get("HB_UI_NO_AUTO_INSTALL") != "1":
                        req_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "requirements.txt"))
                        print(f"installing UI deps: {', '.join(missing)}")
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "-r", req_path],
                            check=True,
                        )
                        missing = _ui_deps_missing()
                    if missing:
                        raise RuntimeError("python-multipart is required for file uploads")
                    from app import server as app_server

                    host = os.environ.get("HB_UI_HOST", "127.0.0.1")
                    app_server.run(host=host, port=args.port)
                except Exception as exc:
                    message = str(exc)
                    if "multipart" in message.lower():
                        print(
                            "error: python-multipart is required for the FastAPI UI. "
                            "Install with: pip install python-multipart",
                            file=sys.stderr,
                        )
                        print("falling back to legacy UI (set HB_UI_LEGACY=1 to force).")
                        host = os.environ.get("HB_UI_HOST", "127.0.0.1")
                        local_ui.serve_local_ui(port=args.port, host=host)
                    else:
                        raise
        elif args.command == "compare":
            run_meta = None
            if args.run_meta:
                run_meta = read_json(args.run_meta)
            if args.source:
                if run_meta is None:
                    run_meta = {}
                run_meta.setdefault("toolchain", {})["source_system"] = args.source
            schema_mode = None if args.schema_mode == "none" else args.schema_mode
            result = run_compare(
                baseline_path=args.baseline,
                run_path=args.run,
                out_dir=args.out,
                schema_mode=schema_mode,
                schema_path=args.schema_path,
                thresholds_path=args.thresholds_path,
                run_meta=run_meta,
            )
            print(f"compare status: {result.status}")
            print(f"report: {result.report_path}")
        elif args.command == "plan":
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            if args.baseline_policy is None:
                args.baseline_policy = parser.get_default("baseline_policy")
            payload = run_plan(
                plan_path=args.plan_path,
                out_dir=args.out,
                metric_registry=args.metric_registry,
                baseline_policy=args.baseline_policy,
                asserts_dir=args.asserts_dir,
            )
            statuses = [item["status"] for item in payload.get("scenarios", [])]
            overall = "PASS"
            if any(status == "FAIL" for status in statuses):
                overall = "FAIL"
            elif any(status == "PASS_WITH_DRIFT" for status in statuses):
                overall = "PASS_WITH_DRIFT"
            elif any(status == "NO_TEST" for status in statuses):
                overall = "NO_TEST"
            print(f"plan status: {overall}")
            if overall == "PASS":
                sys.exit(EXIT_OK)
            if overall == "PASS_WITH_DRIFT":
                sys.exit(PLAN_EXIT_PASS_WITH_DRIFT)
            if overall == "FAIL":
                sys.exit(PLAN_EXIT_FAIL)
            sys.exit(PLAN_EXIT_NO_TEST)
        elif args.command == "bundle":
            import zipfile

            results_dir = args.results_dir
            out_path = args.out or (results_dir.rstrip(os.sep) + ".zip")
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(results_dir):
                    for name in files:
                        full_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_path, results_dir)
                        zf.write(full_path, rel_path)
            print(f"bundle written: {out_path}")
        elif args.command == "adapter":
            if args.adapter_cmd == "vxworks":
                adapter = VxWorksLogAdapter()
                adapter.export(
                    log_path=args.log,
                    out_dir=args.out,
                    baseline_log_path=args.baseline_log,
                    profile_path=args.profile,
                    run_meta=args.run_meta,
                )
                print(f"adapter output: {args.out}")
        elif args.command == "watch":
            watch.run_watch(
                watch_dir=args.dir,
                source=args.source,
                pattern=args.pattern,
                interval=args.interval,
                workspace=args.workspace,
                run_meta=args.run_meta,
                run_meta_dir=args.run_meta_dir,
                open_report=args.open_report,
                once=args.once,
            )
        elif args.command == "feedback":
            if args.feedback_cmd == "record":
                feedback_record(args)
            elif args.feedback_cmd == "export":
                feedback_export(args)
            elif args.feedback_cmd == "serve":
                feedback_serve(args)
        elif args.command == "db":
            script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
            if args.db_cmd == "encrypt":
                script = os.path.join(script_dir, "sqlcipher_encrypt_db.sh")
                subprocess.run(["sh", script, args.input, args.output, args.key], check=True)
            elif args.db_cmd == "decrypt":
                script = os.path.join(script_dir, "sqlcipher_decrypt_db.sh")
                subprocess.run(["sh", script, args.input, args.output, args.key], check=True)
    except HBError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(exc.code)
    except (FileNotFoundError, ValueError) as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        sys.exit(EXIT_PARSE)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(EXIT_UNKNOWN)
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
