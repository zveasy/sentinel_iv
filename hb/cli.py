import argparse
import hashlib
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import yaml

from hb import engine
from hb.adapters import (
    pba_excel_adapter,
    cmapss_fd001,
    cmapss_fd002,
    cmapss_fd003,
    cmapss_fd004,
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


def load_metric_registry(path):
    with open(path, "r") as f:
        registry = yaml.safe_load(f)
    registry["alias_index"] = build_alias_index(registry)
    return registry


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


def load_baseline_policy(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f)
    return payload.get("baseline_policy", payload)


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
    }
    if args.source not in adapter_map:
        raise HBError(f"unknown source adapter: {args.source}", EXIT_CONFIG)

    run_meta = read_json(args.run_meta) if args.run_meta else {}
    run_meta = normalize_run_meta(run_meta, args.source)
    run_id = run_meta["run_id"]

    adapter = adapter_map[args.source]
    if getattr(args, "stream", False) and hasattr(adapter, "parse_stream"):
        metrics_raw = adapter.parse_stream(args.path)
    else:
        metrics_raw = adapter.parse(args.path)
    registry = load_metric_registry(args.metric_registry)
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
    return out_dir


def analyze(args):
    run_dir = args.run
    run_meta = read_json(os.path.join(run_dir, "run_meta_normalized.json"))
    registry = load_metric_registry(args.metric_registry)
    policy = load_baseline_policy(args.baseline_policy)
    registry_hash = file_hash(args.metric_registry)
    redaction_policy = args.redaction_policy
    distribution_enabled = policy.get("distribution_drift_enabled", True)

    conn = init_db(args.db)
    baseline_run_id, baseline_reason, baseline_warning, baseline_match = select_baseline(
        conn, run_meta, policy, registry_hash=registry_hash
    )
    if baseline_run_id:
        baseline_metrics = fetch_metrics(conn, baseline_run_id)
    else:
        baseline_metrics = {}

    metrics_current = {}
    for row in _read_metrics_csv(os.path.join(run_dir, "metrics_normalized.csv")):
        metrics_current[row["metric"]] = {
            "value": float(row["value"]) if row["value"] != "" else None,
            "unit": row.get("unit") or None,
            "tags": row.get("tags") or None,
        }

    (
        status,
        drift_metrics,
        warnings,
        fail_metrics,
        invariant_violations,
        distribution_drifts,
    ) = engine.compare_metrics(
        metrics_current, baseline_metrics, registry, distribution_enabled=distribution_enabled
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

    report_payload = {
        "run_id": report_meta["run_id"],
        "status": status,
        "baseline_run_id": baseline_run_id,
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
        "warnings": warnings,
        "fail_metrics": fail_metrics,
        "invariant_violations": invariant_violations,
    }

    report_dir = os.path.join(args.reports, report_meta["run_id"])
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
    return report_dir


def run(args):
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
    )
    report_dir = analyze(analyze_args)
    print(f"run output: {report_dir}")
    return report_dir


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
