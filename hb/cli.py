import argparse
import hashlib
import os
import sys
import uuid

import yaml

from hb import engine
from hb.adapters import pba_excel_adapter
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
)
from hb.registry_utils import build_alias_index
from hb.report import write_report, write_pdf


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
                "tags": "",
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

    conn = init_db(args.db)
    baseline_run_id, baseline_reason, baseline_warning = select_baseline(
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

    status, drift_metrics, warnings, fail_metrics = engine.compare_metrics(
        metrics_current, baseline_metrics, registry
    )

    report_payload = {
        "run_id": run_meta["run_id"],
        "status": status,
        "baseline_run_id": baseline_run_id,
        "baseline_reason": baseline_reason,
        "baseline_warning": baseline_warning,
        "drift_metrics": drift_metrics,
        "top_drifts": drift_metrics[: args.top],
        "warnings": warnings,
        "fail_metrics": fail_metrics,
    }

    report_dir = os.path.join(args.reports, run_meta["run_id"])
    json_path, html_path = write_report(report_dir, report_payload)
    if getattr(args, "pdf", False):
        pdf_path = os.path.join(report_dir, "drift_report.pdf")
        _, error = write_pdf(html_path, pdf_path)
        if error:
            print(f"pdf export warning: {error}")

    baseline_line = f"baseline: {baseline_run_id or 'none'} ({baseline_reason})"
    print(baseline_line)
    if baseline_warning:
        print(f"baseline warning: {baseline_warning}")

    upsert_run(
        conn,
        run_meta,
        status,
        baseline_run_id=baseline_run_id,
        registry_hash=registry_hash,
    )
    replace_metrics(conn, run_meta["run_id"], _metrics_to_rows(metrics_current))

    write_json(os.path.join(report_dir, "run_meta_normalized.json"), run_meta)
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
    )
    report_dir = analyze(analyze_args)
    print(f"run output: {report_dir}")
    return report_dir


def baseline_set(args):
    conn = init_db(args.db)
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
    parser.add_argument("--metric-registry", default="metric_registry.yaml")
    parser.add_argument("--baseline-policy", default="baseline_policy.yaml")
    parser.add_argument("--db", default="runs.db")
    parser.add_argument("--reports", default=os.path.join("mvp", "reports"))
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

    baseline_parser = subparsers.add_parser("baseline", help="baseline governance")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_cmd", required=True)
    baseline_set_cmd = baseline_sub.add_parser("set", help="set baseline tag")
    baseline_set_cmd.add_argument("run_id")
    baseline_set_cmd.add_argument("--tag", default="golden")
    baseline_list_cmd = baseline_sub.add_parser("list", help="list baseline tags")
    baseline_set_cmd.add_argument("--metric-registry", default=None)
    baseline_set_cmd.add_argument("--db", default=None)
    baseline_list_cmd.add_argument("--db", default=None)
    baseline_list_cmd.add_argument("--metric-registry", default=None)

    runs_parser = subparsers.add_parser("runs", help="run registry")
    runs_sub = runs_parser.add_subparsers(dest="runs_cmd", required=True)
    runs_list_cmd = runs_sub.add_parser("list", help="list recent runs")
    runs_list_cmd.add_argument("--limit", type=int, default=20)
    runs_list_cmd.add_argument("--db", default=None)

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
            run(args)
        elif args.command == "baseline":
            if args.metric_registry is None:
                args.metric_registry = parser.get_default("metric_registry")
            if args.db is None:
                args.db = parser.get_default("db")
            if args.baseline_cmd == "set":
                baseline_set(args)
            elif args.baseline_cmd == "list":
                baseline_list(args)
        elif args.command == "runs":
            if args.db is None:
                args.db = parser.get_default("db")
            if args.runs_cmd == "list":
                runs_list(args)
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
