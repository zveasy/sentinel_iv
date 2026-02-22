import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone, timedelta

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
from hb.normalize import load_telemetry_schema, normalize_telemetry, aggregate_to_metrics
from hb.registry import (
    init_db,
    upsert_run,
    replace_metrics,
    fetch_metrics,
    select_baseline,
    set_baseline_tag,
    list_baseline_tags,
    list_baseline_versions,
    get_baseline_version,
    list_runs,
    add_baseline_approval,
    list_baseline_approvals,
    add_baseline_request,
    list_baseline_requests,
    get_baseline_request,
    set_baseline_request_status,
    count_baseline_approvals,
    run_exists,
    add_baseline_lineage,
    custody_events_list,
    custody_event_insert,
)
from hb.baseline import create_baseline_from_window
from hb.registry_utils import build_alias_index
from hb.audit import append_audit_log, write_artifact_manifest, verify_artifact_manifest, write_config_snapshot_hashes
from hb.report import write_report, write_pdf
from hb.security import load_key, sign_file, verify_signature, encrypt_file
from hb.redaction import apply_redaction
from hb.support import health_check, build_support_bundle
from hb.monitor import write_heartbeat, tail_heartbeats


def file_hash(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:12]


def _require_rbac(operation: str, program: str | None = None) -> None:
    """If HB_RBAC=1, require role permission for operation; raise PermissionError if denied."""
    if os.environ.get("HB_RBAC", "").strip().lower() not in ("1", "true", "yes"):
        return
    from hb.rbac import require_role
    require_role(operation, program)


class HBError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


EXIT_OK = 0
EXIT_UNKNOWN = 1
EXIT_PARSE = 2
EXIT_CONFIG = 3
EXIT_REGISTRY = 4
EXIT_FORBIDDEN = 5

PLAN_EXIT_PASS_WITH_DRIFT = 1
PLAN_EXIT_FAIL = 2
PLAN_EXIT_NO_TEST = 3




def generate_run_id(run_meta):
    if run_meta.get("run_id"):
        return run_meta["run_id"]
    return str(uuid.uuid4())


def normalize_run_meta(run_meta, source_system):
    run_meta.setdefault("run_id", generate_run_id(run_meta))
    if "correlation_id" not in run_meta:
        run_meta["correlation_id"] = os.environ.get("HB_CORRELATION_ID") or str(uuid.uuid4())
    run_meta.setdefault("toolchain", {})
    run_meta["toolchain"]["source_system"] = source_system
    run_meta.setdefault("build", {"git_sha": "", "build_id": ""})
    run_meta.setdefault("timestamps", {"start_utc": "", "end_utc": ""})
    return run_meta


def _baseline_confidence_from_match(baseline_match):
    """Derive baseline confidence (0-1) from baseline_match score for lineage/report."""
    score = baseline_match.get("score")
    if score is not None and isinstance(score, (int, float)):
        return max(0.0, min(1.0, float(score)))
    return 1.0


def _ingest_live(args):
    """Ingest from live source (file_replay, mqtt, syslog)."""
    from hb.ingest import get_source

    perf = getattr(args, "perf", None)
    run_meta = read_json(args.run_meta) if args.run_meta else {}
    run_meta = normalize_run_meta(run_meta, args.source)
    run_id = run_meta["run_id"]

    schema_path = getattr(args, "telemetry_schema", None) or os.environ.get("HB_TELEMETRY_SCHEMA", "config/telemetry_schema.yaml")
    schema = load_telemetry_schema(schema_path) if os.path.isfile(schema_path) else {}

    if args.source == "file_replay":
        delay = getattr(args, "delay_sec", 0.0) or 0.0
        source = get_source("file_replay", path=args.path, delay_sec=delay)
    elif args.source == "mqtt":
        broker = getattr(args, "broker", "tcp://localhost:1883")
        topic = getattr(args, "topic", "hb/metrics/#")
        qos = getattr(args, "qos", 0)
        source = get_source("mqtt", broker=broker, topic=topic, qos=qos)
    else:
        source = get_source("syslog", path=args.path)

    duration = getattr(args, "duration_sec", None) or (5.0 if args.source == "mqtt" else None)
    max_events = getattr(args, "max_events", None)

    try:
        source.connect()
        raw_events = source.read(limit=max_events, timeout_sec=duration)
    finally:
        source.close()

    if not raw_events:
        raw_events = [{"metric": "no_data", "value": 0, "unit": "", "timestamp": datetime.now(timezone.utc).isoformat()}]

    normalized_events = normalize_telemetry(raw_events, schema)
    metrics_raw = aggregate_to_metrics(normalized_events, strategy="last")

    program = run_meta.get("program")
    registry = load_metric_registry(args.metric_registry, program=program)
    metrics_normalized, warnings = engine.normalize_metrics(metrics_raw, registry)

    out_dir = args.out or os.path.join("runs", run_id)
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "run_meta_normalized.json"), run_meta)
    metrics_rows = [{"metric": m, "value": d["value"], "unit": d.get("unit") or "", "tags": d.get("tags") or ""} for m in sorted(metrics_normalized.keys()) for d in [metrics_normalized[m]]]
    write_metrics_csv(os.path.join(out_dir, "metrics_normalized.csv"), metrics_rows)
    if warnings:
        write_json(os.path.join(out_dir, "ingest_warnings.json"), {"warnings": warnings})
    print(f"ingest output: {out_dir}")
    return out_dir


def ingest(args):
    live_sources = {"file_replay", "mqtt", "syslog"}
    if args.source in live_sources:
        return _ingest_live(args)

    from hb.resilience import idempotency_seen, idempotency_record

    run_meta = read_json(args.run_meta) if args.run_meta else {}
    run_meta = normalize_run_meta(run_meta, args.source)
    run_id = run_meta["run_id"]
    out_dir = args.out or os.path.join("runs", run_id)
    key = getattr(args, "idempotency_key", None)
    if key:
        existing = idempotency_seen(key)
        if existing and os.path.isdir(existing) and os.path.isfile(os.path.join(existing, "run_meta_normalized.json")):
            print(f"ingest output (idempotent): {existing}")
            return existing

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
        raise HBError(f"unknown source adapter: {args.source}. Use one of: {list(adapter_map)} or {list(live_sources)}", EXIT_CONFIG)

    perf = getattr(args, "perf", None)

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
    program = run_meta.get("program")
    registry = load_metric_registry(args.metric_registry, program=program)
    compare_plan = load_compare_plan(args.metric_registry, program=program)
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

    if key:
        idempotency_record(key, run_id, out_dir)

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
    from hb.tracing import span
    if getattr(args, "break_glass", False):
        _require_rbac("override")
        if not (getattr(args, "override_reason", "") or "").strip():
            raise HBError("--override-reason is required when using --break-glass", EXIT_CONFIG)
    run_dir = args.run
    with span("hb.analyze", attributes={"run_dir": run_dir} if run_dir else None):
        return _analyze_impl(args)


def _analyze_impl(args):
    run_dir = args.run
    perf = getattr(args, "perf", None)
    if perf is None:
        perf = PerfRecorder()
    run_meta = read_json(os.path.join(run_dir, "run_meta_normalized.json"))
    program = run_meta.get("program")
    operating_mode = run_meta.get("operating_mode")
    registry = load_metric_registry(args.metric_registry, program=program, operating_mode=operating_mode)
    with perf.span("compile_plan"):
        compare_plan = load_compare_plan(args.metric_registry, program=program, operating_mode=operating_mode)
    policy = load_baseline_policy(args.baseline_policy)
    registry_hash = file_hash(args.metric_registry)
    policy_hash = file_hash(args.baseline_policy)
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

    from hb.investigation import build_investigation_hints
    investigation = build_investigation_hints(
        drift_attribution=drift_attribution,
        fail_metrics=fail_metrics,
        invariant_violations=invariant_violations,
        status=status,
        warnings=warnings,
    )

    report_payload = {
        "run_id": report_meta["run_id"],
        "correlation_id": run_meta.get("correlation_id"),
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
        "baseline_confidence": _baseline_confidence_from_match(baseline_match),
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
        "investigation_hints": investigation.get("investigation_hints", []),
        "what_to_do_next": investigation.get("what_to_do_next", ""),
        "primary_issue": investigation.get("primary_issue"),
        "evidence_links": [
            {
                "metric_name": h.get("metric"),
                "artifact_ref": "metrics_normalized.csv",
                "report_ref": "drift_report.json",
                "hint": h.get("pinpoint", ""),
            }
            for h in investigation.get("investigation_hints", [])
        ],
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
    what_next = investigation.get("what_to_do_next")
    if what_next:
        print(f"report: {os.path.join(report_dir, 'drift_report.html')}")
        print(f"what to do next: {what_next[:200]}{'...' if len(what_next) > 200 else ''}")

    config_hashes = write_config_snapshot_hashes(
        getattr(args, "metric_registry", None),
        getattr(args, "baseline_policy", None),
    )
    manifest_path = write_artifact_manifest(
        report_dir,
        [
            json_path,
            html_path,
            pdf_path,
            os.path.join(report_dir, "metrics_normalized.csv"),
            os.path.join(report_dir, "run_meta_normalized.json"),
        ],
        config_hashes=config_hashes if config_hashes else None,
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
    if getattr(args, "break_glass", False) and status == "FAIL":
        expires_at = None
        raw = (getattr(args, "override_expires_in", None) or "24h").strip().lower()
        if raw:
            try:
                if raw.endswith("h"):
                    h = int(raw[:-1])
                    expires_at = (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()
                elif raw.endswith("d"):
                    d = int(raw[:-1])
                    expires_at = (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()
                else:
                    h = int(raw)
                    expires_at = (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()
            except (ValueError, TypeError):
                expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        append_audit_log(
            report_dir,
            report_meta["run_id"],
            "break_glass_override",
            {
                "reason": (getattr(args, "override_reason", None) or "").strip(),
                "operator_id": (getattr(args, "override_operator_id", None) or "").strip() or os.environ.get("HB_OPERATOR_ID", ""),
                "expires_at": expires_at,
            },
        )

    upsert_run(
        conn,
        run_meta,
        status,
        baseline_run_id=baseline_run_id,
        registry_hash=registry_hash,
    )
    add_baseline_lineage(
        conn,
        run_meta["run_id"],
        baseline_run_id,
        registry_hash,
        policy_hash,
        baseline_reason,
        baseline_match.get("level"),
        baseline_match.get("score"),
        baseline_match.get("matched_fields", []),
        baseline_confidence=_baseline_confidence_from_match(baseline_match),
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
    setattr(args, "_analyze_status", status)
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
        break_glass=getattr(args, "break_glass", False),
        override_reason=getattr(args, "override_reason", None),
        override_operator_id=getattr(args, "override_operator_id", None),
        override_expires_in=getattr(args, "override_expires_in", "24h"),
        perf=perf,
    )
    report_dir = analyze(analyze_args)
    setattr(args, "_analyze_status", getattr(analyze_args, "_analyze_status", None))
    print(f"run output: {report_dir}")
    return report_dir


def inject_cmd(args):
    from hb.inject import apply_to_csv
    params = dict(noise_scale=getattr(args, "noise_scale", 0.1), offset=getattr(args, "offset", 0))
    params["metric"] = getattr(args, "metric", "")
    params["value"] = getattr(args, "value", 0.0)
    params["scale"] = getattr(args, "scale", 2.0)
    params["skew_seconds"] = getattr(args, "skew_seconds", 0.0)
    params["drift_per_row"] = getattr(args, "drift_per_row", 0.01)
    params["count"] = getattr(args, "count", 2)
    params["one_shot"] = not getattr(args, "repeat_spike", False)
    apply_to_csv(args.input, args.output, args.fault, **params)
    print(f"wrote {args.output}")


def export_evidence_pack_cmd(args):
    _require_rbac("export evidence-pack")
    out = export_evidence_pack(
        case_id=args.case,
        report_dir=args.report_dir,
        out_path=args.out,
        zip_output=args.zip,
        redaction_policy_path=getattr(args, "redaction_policy", None),
        redaction_profile=getattr(args, "redaction_profile", None),
    )
    print(f"evidence pack: {out}")
    db_path = getattr(args, "db", None)
    if db_path:
        conn = init_db(db_path)
        try:
            custody_event_insert(
                conn,
                event_id=str(uuid.uuid4()),
                case_id=args.case,
                event_type="exported",
                operator_id=getattr(args, "operator_id", None),
                reason="evidence-pack export",
                payload={"out": out},
            )
        finally:
            conn.close()


def custody_timeline_cmd(args):
    """List custody events for a case (run_id)."""
    conn = init_db(args.db)
    events = custody_events_list(conn, case_id=args.case, limit=args.limit)
    conn.close()
    if not events:
        print("no custody events for this case")
        return
    print("event_id | case_id | event_type | ts_utc | operator_id | reason")
    print("---------+---------+------------+--------+-------------+------")
    for e in events:
        reason = (e.get("reason") or "")[:40]
        print(f"{e.get('event_id', '')} | {e.get('case_id', '')} | {e.get('event_type', '')} | {e.get('ts_utc', '')} | {e.get('operator_id') or ''} | {reason}")


def custody_list_cmd(args):
    """List recent custody events across all cases."""
    conn = init_db(args.db)
    events = custody_events_list(conn, case_id=None, limit=args.limit)
    conn.close()
    if not events:
        print("no custody events")
        return
    print("event_id | case_id | event_type | ts_utc | operator_id | reason")
    print("---------+---------+------------+--------+-------------+------")
    for e in events:
        reason = (e.get("reason") or "")[:40]
        print(f"{e.get('event_id', '')} | {e.get('case_id', '')} | {e.get('event_type', '')} | {e.get('ts_utc', '')} | {e.get('operator_id') or ''} | {reason}")


def normalize_cmd(args):
    """hb normalize --schema config/telemetry_schema.yaml --input raw.jsonl --output normalized.csv"""
    import csv
    schema = load_telemetry_schema(args.schema)
    raw_events = []
    with open(args.input, "r", errors="replace") as f:
        if args.input.lower().endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        else:
            reader = csv.DictReader(f)
            for row in reader:
                raw_events.append({
                    "timestamp": row.get("timestamp", ""),
                    "metric": row.get("metric", row.get("name", "")),
                    "value": row.get("value"),
                    "unit": row.get("unit"),
                })
    normalized = normalize_telemetry(raw_events, schema)
    out = args.output
    if out.lower().endswith(".csv"):
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["metric", "value", "unit", "timestamp"])
            w.writeheader()
            for r in normalized:
                w.writerow(r)
        print(f"wrote {out}")
    else:
        os.makedirs(out, exist_ok=True)
        agg = aggregate_to_metrics(normalized, strategy="last")
        rows = [{"metric": m, "value": d["value"], "unit": d.get("unit") or "", "tags": d.get("tags") or ""} for m in sorted(agg.keys()) for d in [agg[m]]]
        write_metrics_csv(os.path.join(out, "metrics_normalized.csv"), rows)
        print(f"wrote {out}/metrics_normalized.csv")


def feedback_record(args):
    payload = feedback.load_feedback_payload(args.input)
    feedback.write_feedback_record(payload, log_path=args.log)
    print(f"feedback recorded: {args.log or feedback.default_log_path()}")


def feedback_export(args):
    feedback.export_feedback(args.log, args.output, mode=args.mode)
    print(f"feedback export written: {args.output}")


def feedback_serve(args):
    feedback.serve_feedback(port=args.port, log_path=args.log)


def support_health(args):
    payload = health_check(args.db, args.metric_registry, args.baseline_policy)
    print(yaml.safe_dump(payload, sort_keys=False))


def support_bundle(args):
    out_path = build_support_bundle(
        out_path=args.out,
        db_path=args.db,
        metric_registry=args.metric_registry,
        baseline_policy=args.baseline_policy,
        report_dir=args.report_dir,
    )
    print(f"support bundle written: {out_path}")


def runtime_cmd(args):
    """Streaming runtime: consume stream, emit decisions continuously (event-time, watermarks, sliding windows)."""
    import yaml as _yaml
    from hb.streaming import StreamingEvaluator, WindowSpec, WatermarkPolicy
    from hb.streaming.evaluator import _config_hashes
    from hb.ingest import get_source
    from hb.normalize import load_telemetry_schema, normalize_telemetry, aggregate_to_metrics
    from hb.config import load_metric_registry, load_baseline_policy
    from hb.registry import init_db, fetch_metrics, select_baseline
    from hb.engine import normalize_metrics, compare_metrics

    if not os.path.isfile(args.config):
        raise HBError(f"runtime config not found: {args.config}", EXIT_CONFIG)
    with open(args.config, "r") as f:
        cfg = _yaml.safe_load(f) or {}
    window_size = float(cfg.get("window_size_sec", 10.0))
    slide = float(cfg.get("slide_sec", 1.0))
    spec = WindowSpec(window_size_sec=window_size, slide_sec=slide)
    policy = WatermarkPolicy(
        allowed_lateness_sec=float(cfg.get("allowed_lateness_sec", 60.0)),
        late_event_policy=cfg.get("late_event_policy", "drop"),
    )
    reg_path = cfg.get("metric_registry", "metric_registry.yaml")
    base_path = cfg.get("baseline_policy", "baseline_policy.yaml")
    registry = load_metric_registry(reg_path)
    base_policy = load_baseline_policy(base_path)
    db_path = cfg.get("db_path", "runs.db")
    conn = init_db(db_path) if os.path.isfile(db_path) else None
    baseline_metrics = {}
    if conn:
        run_meta = {"program": None, "subsystem": None, "test_name": None}
        bid, _, _, _ = select_baseline(conn, run_meta, base_policy)
        if bid:
            baseline_metrics = fetch_metrics(conn, bid) or {}

    def compare_fn(cur, base):
        return compare_metrics(cur, base, registry, distribution_enabled=False, plan=None, early_exit=False, deterministic=True)

    evaluator = StreamingEvaluator(
        window_spec=spec,
        watermark_policy=policy,
        compare_fn=compare_fn,
        metric_registry_path=reg_path,
        baseline_policy_path=base_path,
        max_buckets=cfg.get("max_buckets"),
    )
    baseline_struct = baseline_metrics
    schema_path = cfg.get("telemetry_schema", "config/telemetry_schema.yaml")
    schema = load_telemetry_schema(schema_path) if os.path.isfile(schema_path) else {}
    source_type = cfg.get("source", "file_replay")
    path = cfg.get("path", "")
    if source_type == "file_replay" and path and os.path.isfile(path):
        source = get_source("file_replay", path=path, delay_sec=0)
        source.connect()
        events = source.read(limit=500, timeout_sec=30)
        source.close()
    else:
        print("runtime: set source=file_replay and path= in config to a telemetry.jsonl; exiting after one empty cycle", file=sys.stderr)
        events = []
    for ev in events:
        evaluator.process_event(ev)
    snapshot = evaluator.emit_decision(baseline_struct)
    out_dir = os.path.abspath(cfg.get("output_dir", "runtime_output"))
    os.makedirs(out_dir, exist_ok=True)
    if snapshot:
        write_json(os.path.join(out_dir, "last_decision_snapshot.json"), snapshot.to_dict())
        print(f"decision: {snapshot.decision_payload.get('status')} latency_p95={evaluator.latency.p95()}")
        print(f"snapshot: {out_dir}/last_decision_snapshot.json")
    else:
        print("no decision (no window data)")
    if conn:
        conn.close()


def actions_execute_cmd(args):
    from hb.actions import execute_actions
    from hb.registry import init_db
    db = args.db or os.environ.get("HB_DB_PATH", "runs.db")
    conn = init_db(db) if os.path.isfile(db) else None
    results = execute_actions(
        status=args.status,
        context={},
        policy_path=args.policy,
        dry_run=args.dry_run,
        idempotency_key=args.idempotency_key,
        conn=conn,
        run_id=args.run_id,
        decision_id=args.decision_id,
    )
    print(yaml.safe_dump(results, sort_keys=False))
    for r in results:
        if r.get("status") == "dry_run":
            print("would have done:", r.get("would_have_done"))


def actions_list_cmd(args):
    from hb.registry import init_db, action_ledger_list
    db = args.db or os.environ.get("HB_DB_PATH", "runs.db")
    if not os.path.isfile(db):
        print("db not found:", db)
        return
    conn = init_db(db)
    rows = action_ledger_list(conn, status=args.status, limit=args.limit)
    conn.close()
    print(yaml.safe_dump(rows, sort_keys=False))


def actions_ack_cmd(args):
    from hb.registry import init_db, action_ledger_ack
    import json as _json
    db = args.db or os.environ.get("HB_DB_PATH", "runs.db")
    if not os.path.isfile(db):
        print("db not found:", db)
        return
    conn = init_db(db)
    payload = _json.loads(args.payload) if args.payload else None
    action_ledger_ack(conn, args.action_id, payload)
    conn.close()
    print("acked:", args.action_id)


def readiness_gate(args):
    from hb.readiness import load_readiness_config, evaluate_gate
    config_path = args.config or os.environ.get("HB_READINESS_GATES", "config/readiness_gates.yaml")
    config = load_readiness_config(config_path)
    db = args.db or os.environ.get("HB_DB_PATH", "runs.db")
    conn = init_db(db) if os.path.isfile(db) else None
    try:
        verdict, reasons = evaluate_gate(args.gate, config=config, conn=conn)
        print(f"Gate: {args.gate}")
        print(f"Verdict: {verdict}")
        for r in reasons:
            print(f"  - {r}")
        sys.exit(0 if verdict == "Ready" else 1)
    finally:
        if conn:
            conn.close()


def monitor_heartbeat(args):
    out_path = write_heartbeat(args.log, status=args.status)
    print(f"heartbeat written: {out_path}")


def monitor_tail(args):
    lines = tail_heartbeats(args.log, limit=args.limit)
    for line in lines:
        print(line)


def baseline_set(args):
    _require_rbac("baseline set")
    from hb.baseline_quality import load_baseline_quality_policy, evaluate_baseline_quality
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

    if not getattr(args, "skip_quality_gate", False):
        quality_policy = load_baseline_quality_policy()
        if quality_policy.get("acceptance_criteria"):
            cursor = conn.execute(
                "SELECT program, subsystem, test_name, created_at FROM runs WHERE run_id = ?",
                (args.run_id,),
            )
            row = cursor.fetchone()
            if row:
                program, subsystem, test_name, created_at = row
                since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                cursor2 = conn.execute(
                    "SELECT run_id FROM runs WHERE program = ? AND subsystem = ? AND test_name = ? AND created_at >= ?",
                    (program or "", subsystem or "", test_name or "", since),
                )
                same_context = cursor2.fetchall()
                sample_size = len(same_context) or 1
                time_span_sec = 86400.0
                passed, confidence, reasons = evaluate_baseline_quality(
                    sample_size=sample_size,
                    time_span_sec=time_span_sec,
                    stability_ok=True,
                    no_alerts=True,
                    environment_match_score=1.0,
                    policy=quality_policy,
                )
                if quality_policy.get("require_quality_gate") and not passed:
                    raise HBError(
                        f"baseline quality gate failed: {'; '.join(reasons)}. Use --skip-quality-gate to override.",
                        EXIT_CONFIG,
                    )
                if reasons:
                    print(f"baseline quality: confidence={confidence:.2f}; warnings: {'; '.join(reasons)}")

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


def baseline_create(args):
    db = args.db or os.environ.get("HB_DB_PATH", "runs.db")
    version_id, baseline_run_id = create_baseline_from_window(
        db_path=db,
        window=args.window,
        registry_hash=None,
        out_dir=args.out,
    )
    print(f"created baseline version: {version_id} -> run_id {baseline_run_id}")
    if args.out:
        print(f"artifact dir: {args.out}")


def baseline_promote(args):
    conn = init_db(args.db)
    row = get_baseline_version(conn, args.version)
    if not row:
        raise HBError(f"baseline version not found: {args.version}", EXIT_REGISTRY)
    _version_id, baseline_run_id, _source_run_ids, _created_at, _sig = row
    reg_path = args.metric_registry or os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml")
    registry_hash = file_hash(reg_path) if os.path.isfile(reg_path) else None
    set_baseline_tag(conn, args.tag, baseline_run_id, registry_hash)
    print(f"promoted version {args.version} (run_id={baseline_run_id}) to tag '{args.tag}'")


def baseline_versions_list(args):
    conn = init_db(args.db)
    rows = list_baseline_versions(conn, limit=args.limit)
    if not rows:
        print("no baseline versions found")
        return
    print("version_id | baseline_run_id | source_run_ids | created_at")
    print("-----------+-----------------+----------------+-----------")
    for row in rows:
        print(" | ".join(str(v) for v in row))


def baseline_approve(args):
    _require_rbac("baseline approve")
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
    program = getattr(args, "program", None) or os.environ.get("HB_PROGRAM")
    rows = list_runs(conn, limit=args.limit, program=program)
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
    ingest_parser.add_argument("--source", default="pba_excel", help="pba_excel, cmapss_fd001-004, nasa_http_tsv, smap_msl, custom_tabular, file_replay, mqtt, syslog")
    ingest_parser.add_argument("path", help="file path; for mqtt use . and set --broker/--topic")
    ingest_parser.add_argument("--run-meta", default=None)
    ingest_parser.add_argument("--out", default=None)
    ingest_parser.add_argument("--stream", action="store_true")
    ingest_parser.add_argument("--metric-registry", default=None)
    ingest_parser.add_argument("--telemetry-schema", default=None, help="telemetry_schema.yaml for live sources")
    ingest_parser.add_argument("--duration-sec", type=float, default=None, help="for mqtt/syslog: collect for N seconds")
    ingest_parser.add_argument("--max-events", type=int, default=None, help="max events to collect from live source")
    ingest_parser.add_argument("--broker", default="tcp://localhost:1883", help="MQTT broker URL")
    ingest_parser.add_argument("--topic", default="hb/metrics/#", help="MQTT topic to subscribe")
    ingest_parser.add_argument("--qos", type=int, default=0)
    ingest_parser.add_argument("--delay-sec", type=float, default=0.0, help="file_replay: delay between lines (simulate live)")
    ingest_parser.add_argument("--idempotency-key", default=None, help="if set, skip re-ingest when key was already used; output dir reused")

    normalize_parser = subparsers.add_parser("normalize", help="normalize raw telemetry to canonical metrics (schema + units)")
    normalize_parser.add_argument("--schema", default="config/telemetry_schema.yaml")
    normalize_parser.add_argument("--input", required=True, help="raw events JSONL or CSV")
    normalize_parser.add_argument("--output", required=True, help="output normalized CSV or directory")

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
    analyze_parser.add_argument("--break-glass", action="store_true", help="override gate: proceed despite FAIL; requires --override-reason; logged with expiry")
    analyze_parser.add_argument("--override-reason", default=None, help="required when --break-glass; reason for override")
    analyze_parser.add_argument("--override-operator-id", default=None, help="operator identity for override (or HB_OPERATOR_ID)")
    analyze_parser.add_argument("--override-expires-in", default="24h", help="override expiry e.g. 24h or 7d (default 24h)")

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
    run_parser.add_argument("--break-glass", action="store_true", help="override gate despite FAIL; requires --override-reason")
    run_parser.add_argument("--override-reason", default=None)
    run_parser.add_argument("--override-operator-id", default=None)
    run_parser.add_argument("--override-expires-in", default="24h")

    baseline_parser = subparsers.add_parser("baseline", help="baseline governance")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_cmd", required=True)
    baseline_set_cmd = baseline_sub.add_parser("set", help="set baseline tag")
    baseline_set_cmd.add_argument("run_id")
    baseline_set_cmd.add_argument("--tag", default="golden")
    baseline_set_cmd.add_argument("--force", action="store_true")
    baseline_set_cmd.add_argument("--skip-quality-gate", action="store_true", help="skip baseline quality gate check")
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
    baseline_create_cmd = baseline_sub.add_parser("create", help="create baseline from time window (e.g. 24h, 7d)")
    baseline_create_cmd.add_argument("--window", default="24h", help="24h, 7d, 1h")
    baseline_create_cmd.add_argument("--db", default=None)
    baseline_create_cmd.add_argument("--out", default=None, help="optional dir to write baseline artifact")
    baseline_promote_cmd = baseline_sub.add_parser("promote", help="promote a baseline version to a tag")
    baseline_promote_cmd.add_argument("--version", required=True, help="version_id from baseline list")
    baseline_promote_cmd.add_argument("--tag", default="golden")
    baseline_promote_cmd.add_argument("--db", default=None)
    baseline_promote_cmd.add_argument("--metric-registry", default=None)
    baseline_versions_cmd = baseline_sub.add_parser("versions", help="list baseline versions")
    baseline_versions_cmd.add_argument("--limit", type=int, default=20)
    baseline_versions_cmd.add_argument("--db", default=None)

    runs_parser = subparsers.add_parser("runs", help="run registry")
    runs_sub = runs_parser.add_subparsers(dest="runs_cmd", required=True)
    runs_list_cmd = runs_sub.add_parser("list", help="list recent runs")
    runs_list_cmd.add_argument("--limit", type=int, default=20)
    runs_list_cmd.add_argument("--program", default=None, help="filter by program (or set HB_PROGRAM)")
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

    daemon_parser = subparsers.add_parser("daemon", help="run daemon: continuous ingest + periodic drift check")
    daemon_parser.add_argument("--config", default="config/daemon.yaml")

    runtime_parser = subparsers.add_parser("runtime", help="streaming runtime: event-time, watermarks, sliding windows, continuous decisions")
    runtime_parser.add_argument("--config", default="config/runtime.yaml")

    actions_parser = subparsers.add_parser("actions", help="action/enforcement engine (closed loop)")
    actions_sub = actions_parser.add_subparsers(dest="actions_cmd", required=True)
    actions_execute_cmd = actions_sub.add_parser("execute", help="evaluate policy and record actions (or dry-run)")
    actions_execute_cmd.add_argument("--status", required=True, help="e.g. FAIL, PASS_WITH_DRIFT")
    actions_execute_cmd.add_argument("--policy", default="config/actions_policy.yaml")
    actions_execute_cmd.add_argument("--db", default=None)
    actions_execute_cmd.add_argument("--dry-run", action="store_true")
    actions_execute_cmd.add_argument("--idempotency-key", default=None)
    actions_execute_cmd.add_argument("--run-id", default=None)
    actions_execute_cmd.add_argument("--decision-id", default=None)
    actions_list_cmd = actions_sub.add_parser("list", help="list action ledger entries")
    actions_list_cmd.add_argument("--status", default=None, help="filter by status: pending, acked")
    actions_list_cmd.add_argument("--db", default=None)
    actions_list_cmd.add_argument("--limit", type=int, default=50)
    actions_ack_cmd = actions_sub.add_parser("ack", help="acknowledge an action")
    actions_ack_cmd.add_argument("--action-id", required=True)
    actions_ack_cmd.add_argument("--db", default=None)
    actions_ack_cmd.add_argument("--payload", default=None, help="optional JSON ack payload")

    export_parser = subparsers.add_parser("export", help="export artifacts")
    export_sub = export_parser.add_subparsers(dest="export_cmd", required=True)
    evidence_cmd = export_sub.add_parser("evidence-pack", help="export evidence pack for a case")
    evidence_cmd.add_argument("--case", required=True, help="run_id / case id")
    evidence_cmd.add_argument("--report-dir", required=True)
    evidence_cmd.add_argument("--out", default="evidence_packs")
    evidence_cmd.add_argument("--zip", action="store_true")
    evidence_cmd.add_argument("--redaction-policy", default=None, help="YAML with redact or profiles; use with --redaction-profile")
    evidence_cmd.add_argument("--redaction-profile", default=None, help="named profile (e.g. pii, program_sensitive) for export")
    evidence_cmd.add_argument("--db", default=None, help="record custody event (exported) in this DB after successful export")
    evidence_cmd.add_argument("--operator-id", default=None, help="operator identity for custody record when using --db")

    custody_parser = subparsers.add_parser("custody", help="chain-of-custody events")
    custody_sub = custody_parser.add_subparsers(dest="custody_cmd", required=True)
    _custody_timeline_parser = custody_sub.add_parser("timeline", help="list custody events for a case (run_id)")
    _custody_timeline_parser.add_argument("--case", required=True, help="case id / run_id")
    _custody_timeline_parser.add_argument("--db", default=None)
    _custody_timeline_parser.add_argument("--limit", type=int, default=50)
    _custody_list_parser = custody_sub.add_parser("list", help="list recent custody events across all cases")
    _custody_list_parser.add_argument("--db", default=None)
    _custody_list_parser.add_argument("--limit", type=int, default=50)

    inject_parser = subparsers.add_parser("inject", help="inject fault into CSV (value_corruption, schema_change, time_skew, stuck_at, spike, sensor_drift, duplication)")
    inject_parser.add_argument("--fault", required=True, choices=["value_corruption", "schema_change", "time_skew", "stuck_at", "spike", "sensor_drift", "duplication"])
    inject_parser.add_argument("--input", required=True)
    inject_parser.add_argument("--output", required=True)
    inject_parser.add_argument("--noise-scale", type=float, default=0.1)
    inject_parser.add_argument("--offset", type=float, default=0.0)
    inject_parser.add_argument("--metric", default="", help="metric name for stuck_at, spike, sensor_drift, duplication")
    inject_parser.add_argument("--value", type=float, default=0.0, help="value for stuck_at")
    inject_parser.add_argument("--scale", type=float, default=2.0, help="scale for spike")
    inject_parser.add_argument("--skew-seconds", type=float, default=0.0, help="time skew in seconds for time_skew")
    inject_parser.add_argument("--drift-per-row", type=float, default=0.01, help="drift increment for sensor_drift")
    inject_parser.add_argument("--count", type=int, default=2, help="duplication count for duplication")
    inject_parser.add_argument("--repeat-spike", action="store_true", help="spike every row (default: spike once)")

    replay_parser = subparsers.add_parser("replay", help="defensible replay: same input + config -> compare -> report")
    replay_parser.add_argument("--input-slice", required=True, help="path to metrics CSV or run dir")
    replay_parser.add_argument("--baseline", required=True, help="path to baseline metrics CSV/dir or run_id (with --db)")
    replay_parser.add_argument("--metric-registry", default="metric_registry.yaml")
    replay_parser.add_argument("--baseline-policy", default=None)
    replay_parser.add_argument("--db", default=None)
    replay_parser.add_argument("--out", default="replay_output")

    support_parser = subparsers.add_parser("support", help="support diagnostics")
    support_sub = support_parser.add_subparsers(dest="support_cmd", required=True)
    support_health_cmd = support_sub.add_parser("health", help="run health checks")
    support_health_cmd.add_argument("--db", default=None)
    support_health_cmd.add_argument("--metric-registry", default=None)
    support_health_cmd.add_argument("--baseline-policy", default=None)
    support_bundle_cmd = support_sub.add_parser("bundle", help="write a support bundle zip")
    support_bundle_cmd.add_argument("--out", default="support_bundle.zip")
    support_bundle_cmd.add_argument("--db", default=None)
    support_bundle_cmd.add_argument("--metric-registry", default=None)
    support_bundle_cmd.add_argument("--baseline-policy", default=None)
    support_bundle_cmd.add_argument("--report-dir", default=None)

    monitor_parser = subparsers.add_parser("monitor", help="monitoring hooks")
    monitor_sub = monitor_parser.add_subparsers(dest="monitor_cmd", required=True)
    monitor_heartbeat_cmd = monitor_sub.add_parser("heartbeat", help="write a heartbeat entry")
    monitor_heartbeat_cmd.add_argument("--log", default="artifacts/heartbeat.jsonl")
    monitor_heartbeat_cmd.add_argument("--status", default="ok")
    monitor_tail_cmd = monitor_sub.add_parser("tail", help="tail heartbeat entries")
    monitor_tail_cmd.add_argument("--log", default="artifacts/heartbeat.jsonl")
    monitor_tail_cmd.add_argument("--limit", type=int, default=20)

    health_parser = subparsers.add_parser("health", help="health and Prometheus metrics endpoints")
    health_sub = health_parser.add_subparsers(dest="health_cmd", required=True)
    health_serve_cmd = health_sub.add_parser("serve", help="serve /ready, /live, /metrics HTTP")
    health_serve_cmd.add_argument("--port", type=int, default=int(os.environ.get("HB_HEALTH_PORT", "9090")))
    health_serve_cmd.add_argument("--bind", default="0.0.0.0", help="bind address")
    health_serve_cmd.add_argument("--db", default=None, help="DB path for /ready check")
    health_serve_cmd.add_argument("--metrics-file", default=None, help="optional: write metrics to file for scrape")
    health_serve_cmd.add_argument("--config", default=None, help="optional daemon config path for /ready")

    readiness_parser = subparsers.add_parser("readiness", help="program readiness gate (PREWG)")
    readiness_sub = readiness_parser.add_subparsers(dest="readiness_cmd", required=True)
    readiness_gate_cmd = readiness_sub.add_parser("gate", help="evaluate a readiness gate")
    readiness_gate_cmd.add_argument("--gate", required=True, help="e.g. Pre-CDR, Pre-Flight, Regression-Exit")
    readiness_gate_cmd.add_argument("--config", default=None)
    readiness_gate_cmd.add_argument("--db", default=None)

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
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            ingest(args)
        elif args.command == "normalize":
            normalize_cmd(args)
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
            if os.environ.get("HB_GATE_FAIL_EXIT", "").strip().lower() in ("1", "true", "yes"):
                if getattr(args, "_analyze_status", None) == "FAIL":
                    if getattr(args, "break_glass", False):
                        pass
                    else:
                        sys.exit(PLAN_EXIT_FAIL)
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
            if os.environ.get("HB_GATE_FAIL_EXIT", "").strip().lower() in ("1", "true", "yes"):
                if getattr(args, "_analyze_status", None) == "FAIL":
                    if getattr(args, "break_glass", False):
                        pass
                    else:
                        sys.exit(PLAN_EXIT_FAIL)
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
            elif args.baseline_cmd == "create":
                baseline_create(args)
            elif args.baseline_cmd == "promote":
                baseline_promote(args)
            elif args.baseline_cmd == "versions":
                baseline_versions_list(args)
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
        elif args.command == "daemon":
            if not os.path.isfile(args.config):
                print(f"daemon config not found: {args.config}", file=sys.stderr)
                sys.exit(EXIT_CONFIG)
            from hb.daemon import daemon_main
            daemon_main(args.config)
        elif args.command == "runtime":
            if not os.path.isfile(args.config):
                print(f"runtime config not found: {args.config}", file=sys.stderr)
                sys.exit(EXIT_CONFIG)
            runtime_cmd(args)
        elif args.command == "actions":
            if args.actions_cmd == "execute":
                actions_execute_cmd(args)
            elif args.actions_cmd == "list":
                actions_list_cmd(args)
            elif args.actions_cmd == "ack":
                actions_ack_cmd(args)
        elif args.command == "export":
            if args.export_cmd == "evidence-pack":
                export_evidence_pack_cmd(args)
        elif args.command == "custody":
            if args.db is None:
                args.db = parser.get_default("db")
            if args.custody_cmd == "timeline":
                custody_timeline_cmd(args)
            elif args.custody_cmd == "list":
                custody_list_cmd(args)
        elif args.command == "inject":
            inject_cmd(args)
        elif args.command == "health":
            if args.health_cmd == "serve":
                from hb.health_server import serve
                db_path = getattr(args, "db", None) or os.environ.get("HB_DB_PATH")
                serve(
                    bind=getattr(args, "bind", "0.0.0.0"),
                    port=args.port,
                    db_path=db_path,
                    config_path=getattr(args, "config", None),
                    metrics_file_path=getattr(args, "metrics_file", None),
                )
            else:
                raise HBError("health subcommand required", EXIT_USAGE)
        elif args.command == "replay":
            from hb.replay import replay_decision
            result = replay_decision(
                args.input_slice,
                args.baseline,
                args.metric_registry,
                baseline_policy_path=args.baseline_policy,
                db_path=args.db,
                out_dir=args.out,
            )
            print(json.dumps(result, indent=2))
            print(f"report: {args.out}")
        elif args.command == "support":
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            if args.baseline_policy is None:
                args.baseline_policy = parser.get_default("baseline_policy")
            if args.db is None:
                args.db = parser.get_default("db")
            if args.support_cmd == "health":
                support_health(args)
            elif args.support_cmd == "bundle":
                support_bundle(args)
        elif args.command == "readiness":
            if args.readiness_cmd == "gate":
                readiness_gate(args)
        elif args.command == "monitor":
            if args.monitor_cmd == "heartbeat":
                monitor_heartbeat(args)
            elif args.monitor_cmd == "tail":
                monitor_tail(args)
        elif args.command == "db":
            if args.db_cmd == "encrypt":
                _require_rbac("db encrypt")
            elif args.db_cmd == "decrypt":
                _require_rbac("db decrypt")
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
    except PermissionError as exc:
        print(f"forbidden: {exc}", file=sys.stderr)
        sys.exit(EXIT_FORBIDDEN)
    except (FileNotFoundError, ValueError) as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        sys.exit(EXIT_PARSE)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(EXIT_UNKNOWN)
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
