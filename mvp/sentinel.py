#!/usr/bin/env python3
import argparse
import importlib
import json
import os
import sys

from mvp import analyze


def load_pipeline(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except OSError as exc:
        raise analyze.ConfigError(f"pipeline file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise analyze.ConfigError(f"invalid pipeline JSON: {path}") from exc


def load_plugin(module_path, attr):
    module = importlib.import_module(module_path)
    if not hasattr(module, attr):
        raise analyze.ConfigError(f"plugin missing {attr}(): {module_path}")
    return getattr(module, attr)


def resolve_source(source, pipeline):
    sources = pipeline.get("sources", {})
    if source not in sources:
        raise analyze.ConfigError(f"unknown source: {source}")
    return sources[source]


def resolve_baseline(baseline_arg, conn, config_hash):
    if baseline_arg and os.path.exists(baseline_arg):
        return baseline_arg, None
    tag = baseline_arg or "golden"
    tag_info = analyze.get_baseline_tag(conn, tag)
    if not tag_info:
        raise analyze.ConfigError(f"baseline tag not found: {tag}")
    if config_hash and tag_info.get("config_hash") and config_hash != tag_info["config_hash"]:
        analyze.log(
            f"warning: baseline config hash mismatch ({tag_info['config_hash']} != {config_hash})",
            "error",
        )
    return tag_info["run_path"], tag_info


def run_analyze(args):
    pipeline = load_pipeline(args.pipeline)
    source = resolve_source(args.source, pipeline)
    parser_fn = load_plugin(source["parser"], "parse")
    metrics_fn = load_plugin(source["metrics"], "apply")

    raw_metrics = parser_fn(args.run)
    schema = analyze.load_schema(source["schema"])
    metrics = analyze.apply_schema(raw_metrics, schema)
    metrics = metrics_fn(metrics)

    if args.baseline and os.path.exists(args.baseline):
        baseline_raw = parser_fn(args.baseline)
        baseline_metrics = analyze.apply_schema(baseline_raw, schema)
    else:
        baseline_metrics = None

    thresholds = analyze.load_thresholds(args.config) if os.path.exists(args.config) else {}
    templates = (
        analyze.load_templates(args.templates_config)
        if args.templates_config and os.path.exists(args.templates_config)
        else {}
    )
    template_name = args.template
    template_metrics = None
    if template_name:
        if template_name not in templates:
            raise analyze.ConfigError(f"unknown template: {template_name}")
        template_metrics = templates[template_name]

    conn = analyze.init_registry(args.registry)
    config_hash = analyze.file_hash(args.config)[:12] if args.config and os.path.exists(args.config) else None
    baseline_path, tag_info = resolve_baseline(args.baseline, conn, config_hash)

    if baseline_metrics is None:
        baseline_raw = parser_fn(baseline_path)
        baseline_metrics = analyze.apply_schema(baseline_raw, schema)

    analyze.validate_metrics("Baseline", baseline_metrics)
    analyze.validate_metrics("Current", metrics)

    comparison = analyze.compare_metrics(
        baseline_metrics, metrics, thresholds, template_metrics
    )
    summary = analyze.summarize(comparison)

    run_id = args.run_id or analyze.compute_run_id(args.run, baseline_path, args.config)
    baseline_id = analyze.file_hash(baseline_path)[:12]
    report_dir = args.out or os.path.join("mvp", "reports", run_id)
    os.makedirs(report_dir, exist_ok=True)

    diff_payload = {
        "run_id": run_id,
        "baseline_id": baseline_id,
        "baseline_tag": tag_info["tag"] if tag_info else None,
        "summary": summary,
        "config_hash": config_hash,
        "template": template_name,
        "metrics": comparison,
        "notes": "",
    }
    diff_path = os.path.join(report_dir, "run-diff.json")
    with open(diff_path, "w") as f:
        json.dump(diff_payload, f, indent=2)

    summary_path = os.path.join(report_dir, "run-summary.txt")
    with open(summary_path, "w") as f:
        f.write(summary + "\n")

    drift_count = sum(1 for m in comparison if m["status"] == "drift")
    report_html = analyze.render_report(
        run_id,
        baseline_id,
        summary,
        comparison,
        drift_count,
        config_hash,
        thresholds,
        template_name,
    )
    report_path = os.path.join(report_dir, "run-report.html")
    with open(report_path, "w") as f:
        f.write(report_html)

    created_at = analyze.datetime.now(analyze.timezone.utc).isoformat()
    analyze.upsert_run(
        conn,
        {
            "run_id": run_id,
            "baseline_id": baseline_id,
            "run_path": os.path.abspath(args.run),
            "baseline_path": os.path.abspath(baseline_path),
            "config_path": os.path.abspath(args.config) if args.config else "",
            "config_hash": config_hash,
            "summary": summary,
            "metrics_count": len(comparison),
            "drift_count": drift_count,
            "created_at": created_at,
            "report_dir": os.path.abspath(report_dir),
            "report_path": os.path.abspath(report_path),
            "diff_path": os.path.abspath(diff_path),
            "summary_path": os.path.abspath(summary_path),
        },
    )


def run_baseline_set(args):
    conn = analyze.init_registry(args.registry)
    run = analyze.get_run(conn, args.run_id)
    config_hash = run["config_hash"]
    if not config_hash and run["config_path"] and os.path.exists(run["config_path"]):
        config_hash = analyze.file_hash(run["config_path"])[:12]
    analyze.set_baseline_tag(conn, args.tag, run["run_id"], run["run_path"], config_hash)
    print(f"baseline tag set: {args.tag} -> {run['run_id']}")


def run_baseline_list(args):
    conn = analyze.init_registry(args.registry)
    rows = analyze.list_baseline_tags(conn)
    if not rows:
        print("no baseline tags found")
        return
    print("tag | run_id | run_path | config_hash | created_at")
    print("----+--------+----------+-------------+-----------")
    for row in rows:
        print(" | ".join(str(value) for value in row))


def main():
    parser = argparse.ArgumentParser(description="Sentinel-IV internal lab CLI")
    parser.add_argument(
        "--registry",
        default="mvp/registry/runs.db",
        help="SQLite registry path",
    )
    parser.add_argument(
        "--config",
        default="mvp/config/thresholds.yaml",
        help="thresholds config (YAML)",
    )
    parser.add_argument(
        "--templates-config",
        default="mvp/config/metric-templates.yaml",
        help="metric templates config",
    )
    parser.add_argument(
        "--pipeline",
        default="mvp/config/pipeline.json",
        help="pipeline config",
    )
    parser.add_argument("--verbose", action="store_true", help="verbose logging")
    parser.add_argument("--quiet", action="store_true", help="suppress non-error output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="analyze a run")
    analyze_parser.add_argument("run", help="run file path")
    analyze_parser.add_argument("--source", default="basic_csv", help="source name")
    analyze_parser.add_argument("--baseline", default=None, help="baseline tag or file")
    analyze_parser.add_argument("--out", default=None, help="output directory")
    analyze_parser.add_argument("--run-id", default=None, help="override run ID")
    analyze_parser.add_argument("--template", default=None, help="template name to filter metrics")

    baseline_parser = subparsers.add_parser("baseline", help="manage baselines")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_cmd", required=True)
    baseline_set = baseline_sub.add_parser("set", help="set baseline tag")
    baseline_set.add_argument("run_id", help="run ID to tag")
    baseline_set.add_argument("--tag", default="golden", help="baseline tag")
    baseline_list = baseline_sub.add_parser("list", help="list baseline tags")

    args = parser.parse_args()

    if args.quiet:
        analyze.LOG_LEVEL = "error"
    elif args.verbose:
        analyze.LOG_LEVEL = "debug"

    try:
        if args.command == "analyze":
            run_analyze(args)
        elif args.command == "baseline":
            if args.baseline_cmd == "set":
                run_baseline_set(args)
            elif args.baseline_cmd == "list":
                run_baseline_list(args)
    except analyze.ParseError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        sys.exit(analyze.EXIT_PARSE)
    except analyze.ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        sys.exit(analyze.EXIT_VALIDATE)
    except analyze.ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        sys.exit(analyze.EXIT_CONFIG)
    except analyze.RegistryError as exc:
        print(f"registry error: {exc}", file=sys.stderr)
        sys.exit(analyze.EXIT_REGISTRY)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(analyze.EXIT_UNKNOWN)


if __name__ == "__main__":
    main()
