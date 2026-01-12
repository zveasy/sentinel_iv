#!/usr/bin/env python3
import argparse
import csv
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone


class ParseError(Exception):
    pass


class ValidationError(Exception):
    pass


class ConfigError(Exception):
    pass


class RegistryError(Exception):
    pass


EXIT_PARSE = 2
EXIT_VALIDATE = 3
EXIT_CONFIG = 4
EXIT_REGISTRY = 5
EXIT_UNKNOWN = 1

LOG_LEVEL = "info"
LOG_ORDER = {"debug": 10, "info": 20, "error": 30}


def log(message, level="info"):
    if LOG_ORDER[level] < LOG_ORDER[LOG_LEVEL]:
        return
    print(message, file=sys.stderr)


def parse_number(value):
    try:
        if value is None:
            return None
        value = str(value).strip()
        if value == "":
            return None
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return None


def parse_value(value):
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return value, None
    text = str(value).strip()
    if text == "":
        return None, None
    match = re.match(r"^([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-zA-Z]+)?$", text)
    if not match:
        raise ParseError(f"invalid metric value: {value}")
    number_text = match.group(1)
    number = parse_number(number_text)
    if number is None:
        raise ParseError(f"invalid metric value: {value}")
    unit = match.group(2).lower() if match.group(2) else None
    return number, unit


def load_schema(path):
    try:
        with open(path, "r") as f:
            schema = json.load(f)
    except OSError as exc:
        raise ConfigError(f"schema file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid schema JSON: {path}") from exc
    return schema


def apply_schema(metrics, schema):
    mapping = schema.get("mapping", {})
    defaults = schema.get("defaults", {})
    required = schema.get("required", [])
    optional = schema.get("optional", [])
    allow_extra = schema.get("allow_extra", True)

    normalized = {}
    for key, value in metrics.items():
        mapped = mapping.get(key, key)
        normalized[mapped] = value

    for key, value in defaults.items():
        if key not in normalized:
            normalized[key] = parse_value(value)

    missing = [key for key in required if key not in normalized or normalized[key][0] is None]
    if missing:
        missing_str = ", ".join(missing)
        raise ValidationError(f"missing required metrics: {missing_str}")

    if not allow_extra:
        allowed = set(required) | set(optional) | set(defaults.keys())
        unknown = [key for key in normalized.keys() if key not in allowed]
        if unknown:
            unknown_str = ", ".join(unknown)
            raise ValidationError(f"unexpected metrics present: {unknown_str}")

    return normalized


def file_hash(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_run_id(run_path, baseline_path, config_path):
    hasher = hashlib.sha256()
    for path in [run_path, baseline_path]:
        hasher.update(file_hash(path).encode("utf-8"))
    if config_path and os.path.exists(config_path):
        hasher.update(file_hash(config_path).encode("utf-8"))
    return hasher.hexdigest()[:12]


def load_metrics_csv(path):
    metrics = {}
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ParseError("CSV missing header row")
        fieldnames = [name.strip().lower() for name in reader.fieldnames]
        if "metric" not in fieldnames or "value" not in fieldnames:
            raise ParseError("CSV must include 'metric' and 'value' columns")
        metric_idx = fieldnames.index("metric")
        value_idx = fieldnames.index("value")
        for row in reader:
            values = list(row.values())
            metric_name = values[metric_idx].strip()
            if metric_name == "":
                continue
            metrics[metric_name] = parse_value(values[value_idx])
    return metrics


def load_metrics_excel(path):
    try:
        import openpyxl
    except ImportError as exc:
        raise ConfigError(
            "Excel ingestion requires openpyxl. Install with: pip install openpyxl"
        ) from exc

    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return {}

    headers = [str(cell).strip().lower() for cell in rows[0] if cell is not None]
    if "metric" not in headers or "value" not in headers:
        raise ParseError("Excel sheet must include 'metric' and 'value' columns")
    metric_idx = headers.index("metric")
    value_idx = headers.index("value")

    metrics = {}
    for row in rows[1:]:
        if row is None or len(row) <= max(metric_idx, value_idx):
            continue
        metric_cell = row[metric_idx]
        value_cell = row[value_idx]
        if metric_cell is None:
            continue
        metric_name = str(metric_cell).strip()
        if metric_name == "":
            continue
        metrics[metric_name] = parse_value(value_cell)
    return metrics


def load_metrics_log(path):
    metrics = {}
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if line == "" or line.startswith("#") or line.startswith("//"):
                continue
            if "," in line:
                parts = line.split(",", 1)
            elif ":" in line:
                parts = line.split(":", 1)
            elif "=" in line:
                parts = line.split("=", 1)
            else:
                continue
            metric_name = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""
            if metric_name == "":
                continue
            metrics[metric_name] = parse_value(value)
    return metrics


def load_metrics(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in [".csv"]:
        return load_metrics_csv(path)
    if ext in [".xlsx", ".xlsm"]:
        return load_metrics_excel(path)
    if ext in [".txt", ".log"]:
        return load_metrics_log(path)
    raise ParseError(f"unsupported input format: {ext}")


def validate_metrics(label, metrics):
    if not metrics:
        raise ValidationError(f"{label} metrics file produced no metrics")
    missing = [name for name, value in metrics.items() if value[0] is None]
    if missing:
        missing_str = ", ".join(missing)
        raise ValidationError(f"{label} metrics missing values for: {missing_str}")


def normalize_metric_value(name, value_tuple, thresholds):
    value, unit = value_tuple
    if value is None:
        return None, None
    config = thresholds.get(name, {})
    unit_map = config.get("unit_map") or {}
    canonical = config.get("unit")
    if unit is None:
        return value, canonical
    if unit_map:
        if unit not in unit_map:
            raise ValidationError(f"unsupported unit for {name}: {unit}")
        return value * unit_map[unit], canonical or unit
    raise ValidationError(f"unit provided for {name} but no unit_map configured")


def load_thresholds(path):
    thresholds = {}
    current_metric = None
    in_metrics = False
    in_unit_map = False
    with open(path, "r") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.strip() == "" or line.strip().startswith("#"):
                continue
            if line.strip() == "metrics:":
                in_metrics = True
                continue
            if not in_metrics:
                continue
            if line.startswith("  ") and not line.startswith("    "):
                key = line.strip().rstrip(":")
                current_metric = key
                thresholds[current_metric] = {
                    "drift_threshold": None,
                    "type": None,
                    "unit": None,
                    "unit_map": {},
                }
                in_unit_map = False
                continue
            if line.startswith("      ") and current_metric and in_unit_map:
                entry = line.strip()
                if ":" in entry:
                    key, value = entry.split(":", 1)
                    thresholds[current_metric]["unit_map"][key.strip().lower()] = parse_number(
                        value.strip()
                    )
                continue
            if line.startswith("    ") and current_metric:
                entry = line.strip()
                if entry.startswith("drift_threshold:"):
                    value = entry.split(":", 1)[1].strip()
                    thresholds[current_metric]["drift_threshold"] = parse_number(value)
                    in_unit_map = False
                elif entry.startswith("type:"):
                    thresholds[current_metric]["type"] = entry.split(":", 1)[1].strip()
                    in_unit_map = False
                elif entry.startswith("unit:"):
                    thresholds[current_metric]["unit"] = entry.split(":", 1)[1].strip().lower()
                    in_unit_map = False
                elif entry.startswith("unit_map:"):
                    in_unit_map = True
    return thresholds


def load_templates(path):
    templates = {}
    current_template = None
    in_templates = False
    with open(path, "r") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.strip() == "" or line.strip().startswith("#"):
                continue
            if line.strip() == "templates:":
                in_templates = True
                continue
            if not in_templates:
                continue
            if line.startswith("  ") and not line.startswith("    "):
                current_template = line.strip().rstrip(":")
                templates[current_template] = []
                continue
            if line.startswith("    -") and current_template:
                metric = line.split("-", 1)[1].strip()
                if metric:
                    templates[current_template].append(metric)
    return templates


def init_registry(path):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                baseline_id TEXT,
                run_path TEXT,
                baseline_path TEXT,
                config_path TEXT,
                config_hash TEXT,
                summary TEXT,
                metrics_count INTEGER,
                drift_count INTEGER,
                created_at TEXT,
                report_dir TEXT,
                report_path TEXT,
                diff_path TEXT,
                summary_path TEXT
            )
            """
        )
        cursor = conn.execute("PRAGMA table_info(runs)")
        columns = {row[1] for row in cursor.fetchall()}
        if "config_hash" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN config_hash TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS baseline_tags (
                tag TEXT PRIMARY KEY,
                run_id TEXT,
                run_path TEXT,
                config_hash TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
        return conn
    except sqlite3.Error as exc:
        raise RegistryError(f"failed to init registry: {exc}") from exc


def upsert_run(conn, payload):
    try:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, baseline_id, run_path, baseline_path, config_path, config_hash, summary,
                metrics_count, drift_count, created_at, report_dir, report_path,
                diff_path, summary_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                config_hash=excluded.config_hash,
                summary=excluded.summary,
                metrics_count=excluded.metrics_count,
                drift_count=excluded.drift_count,
                created_at=excluded.created_at,
                report_dir=excluded.report_dir,
                report_path=excluded.report_path,
                diff_path=excluded.diff_path,
                summary_path=excluded.summary_path
            """,
            (
                payload["run_id"],
                payload["baseline_id"],
                payload["run_path"],
                payload["baseline_path"],
                payload["config_path"],
                payload["config_hash"],
                payload["summary"],
                payload["metrics_count"],
                payload["drift_count"],
                payload["created_at"],
                payload["report_dir"],
                payload["report_path"],
                payload["diff_path"],
                payload["summary_path"],
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise RegistryError(f"failed to write registry: {exc}") from exc


def get_run(conn, run_id):
    cursor = conn.execute(
        "SELECT run_id, run_path, config_path, config_hash FROM runs WHERE run_id = ?",
        (run_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise RegistryError(f"run not found: {run_id}")
    return {
        "run_id": row[0],
        "run_path": row[1],
        "config_path": row[2],
        "config_hash": row[3],
    }


def set_baseline_tag(conn, tag, run_id, run_path, config_hash):
    try:
        conn.execute(
            """
            INSERT INTO baseline_tags (tag, run_id, run_path, config_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tag) DO UPDATE SET
                run_id=excluded.run_id,
                run_path=excluded.run_path,
                config_hash=excluded.config_hash,
                created_at=excluded.created_at
            """,
            (
                tag,
                run_id,
                run_path,
                config_hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise RegistryError(f"failed to set baseline tag: {exc}") from exc


def get_baseline_tag(conn, tag):
    cursor = conn.execute(
        "SELECT tag, run_id, run_path, config_hash FROM baseline_tags WHERE tag = ?",
        (tag,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "tag": row[0],
        "run_id": row[1],
        "run_path": row[2],
        "config_hash": row[3],
    }


def list_baseline_tags(conn):
    cursor = conn.execute(
        "SELECT tag, run_id, run_path, config_hash, created_at FROM baseline_tags ORDER BY created_at DESC"
    )
    return cursor.fetchall()


def compare_metrics(baseline, current, thresholds, metric_names=None):
    metrics = []
    if metric_names is None:
        metric_names = sorted(set(baseline.keys()) | set(current.keys()))
    for name in metric_names:
        base_raw = baseline.get(name)
        curr_raw = current.get(name)
        config = thresholds.get(name, {})
        threshold = config.get("drift_threshold")
        if name not in baseline:
            status = "missing_baseline"
            delta = None
            unit = config.get("unit")
            base_val = None
            curr_val = None
        elif name not in current:
            status = "missing_current"
            delta = None
            unit = config.get("unit")
            base_val = None
            curr_val = None
        else:
            base_val, base_unit = normalize_metric_value(name, base_raw, thresholds)
            curr_val, curr_unit = normalize_metric_value(name, curr_raw, thresholds)
            unit = config.get("unit") or base_unit or curr_unit
            if base_val is None or curr_val is None:
                delta = None
                status = "missing_value"
            else:
                delta = curr_val - base_val
                if threshold is not None and abs(delta) > threshold:
                    status = "drift"
                else:
                    status = "ok"
        metrics.append(
            {
                "name": name,
                "baseline": base_val,
                "current": curr_val,
                "delta": delta,
                "threshold": threshold,
                "unit": unit,
                "status": status,
            }
        )
    return metrics


def summarize(metrics):
    statuses = {m["status"] for m in metrics}
    if "missing_baseline" in statuses or "missing_current" in statuses or "missing_value" in statuses:
        return "FAIL"
    if "drift" in statuses:
        return "PASS-with-drift"
    return "PASS"


def render_report(run_id, baseline_id, summary, metrics, drift_count, config_hash, thresholds, template_name):
    rows = []
    for m in metrics:
        status_class = f"status-{m['status']}"
        rows.append(
            f"<tr class=\"{status_class}\">"
            f"<td>{m['name']}</td>"
            f"<td>{m['baseline']}</td>"
            f"<td>{m['current']}</td>"
            f"<td>{m['delta']}</td>"
            f"<td>{m['threshold']}</td>"
            f"<td>{m['unit'] or ''}</td>"
            f"<td>{m['status']}</td>"
            "</tr>"
        )
    table_rows = "\n".join(rows)
    thresholds_block = html.escape(json.dumps(thresholds, indent=2, sort_keys=True))
    template_line = f"Template: {template_name}" if template_name else "Template: none"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Sentinel-IV MVP Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    h1 {{ margin-bottom: 6px; }}
    .meta {{ color: #444; margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f3f3; }}
    .status-drift {{ background: #fff2cc; }}
    .status-missing_baseline {{ background: #f8d7da; }}
    .status-missing_current {{ background: #f8d7da; }}
    .status-missing_value {{ background: #f8d7da; }}
    .status {{ font-weight: bold; }}
    details {{ margin-top: 16px; }}
    pre {{ background: #f8f9fa; padding: 12px; }}
  </style>
</head>
<body>
  <h1>Run Health Report</h1>
  <div class="meta">Run ID: {run_id} | Baseline: {baseline_id}</div>
  <div class="status">Summary: {summary}</div>
  <div class="meta">Metrics: {len(metrics)} | Drift: {drift_count}</div>
  <h2>Metric Comparison</h2>
  <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Baseline</th>
        <th>Current</th>
        <th>Delta</th>
        <th>Threshold</th>
        <th>Unit</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
  <details>
    <summary>Config</summary>
    <pre>Config hash: {config_hash or 'none'}\n{template_line}</pre>
    <pre>{thresholds_block}</pre>
  </details>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Sentinel-IV MVP analyzer")
    parser.add_argument("--run", required=True, help="current run file (CSV)")
    parser.add_argument("--baseline", required=True, help="baseline run file (CSV)")
    parser.add_argument(
        "--config",
        default="mvp/config/thresholds.yaml",
        help="thresholds config (YAML)",
    )
    parser.add_argument(
        "--out", default=None, help="output directory"
    )
    parser.add_argument(
        "--format",
        default="html",
        choices=["html"],
        help="report format",
    )
    parser.add_argument("--run-id", default=None, help="override run ID")
    parser.add_argument(
        "--registry",
        default="mvp/registry/runs.db",
        help="SQLite registry path",
    )
    parser.add_argument(
        "--templates-config",
        default="mvp/config/metric-templates.yaml",
        help="metric templates config",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="template name from templates config",
    )
    parser.add_argument("--verbose", action="store_true", help="verbose logging")
    parser.add_argument("--quiet", action="store_true", help="suppress non-error output")
    args = parser.parse_args()

    global LOG_LEVEL
    if args.quiet:
        LOG_LEVEL = "error"
    elif args.verbose:
        LOG_LEVEL = "debug"

    try:
        log("loading metrics", "debug")
        baseline_metrics = load_metrics(args.baseline)
        current_metrics = load_metrics(args.run)
        thresholds = load_thresholds(args.config) if os.path.exists(args.config) else {}
        templates = (
            load_templates(args.templates_config)
            if args.templates_config and os.path.exists(args.templates_config)
            else {}
        )
        template_metrics = None
        template_name = None
        if args.template:
            if args.template not in templates:
                raise ConfigError(f"unknown template: {args.template}")
            template_name = args.template
            template_metrics = templates[args.template]

        validate_metrics("Baseline", baseline_metrics)
        validate_metrics("Current", current_metrics)
        comparison = compare_metrics(
            baseline_metrics, current_metrics, thresholds, template_metrics
        )
        summary = summarize(comparison)

        run_id = args.run_id or compute_run_id(args.run, args.baseline, args.config)
        baseline_id = file_hash(args.baseline)[:12]
        report_dir = args.out or os.path.join("mvp", "reports", run_id)
        os.makedirs(report_dir, exist_ok=True)
        config_hash = file_hash(args.config)[:12] if args.config and os.path.exists(args.config) else None

        diff_payload = {
            "run_id": run_id,
            "baseline_id": baseline_id,
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
        report_html = render_report(
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

        conn = init_registry(args.registry)
        created_at = datetime.now(timezone.utc).isoformat()
        upsert_run(
            conn,
            {
                "run_id": run_id,
                "baseline_id": baseline_id,
                "run_path": os.path.abspath(args.run),
                "baseline_path": os.path.abspath(args.baseline),
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
    except ParseError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        sys.exit(EXIT_PARSE)
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        sys.exit(EXIT_VALIDATE)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    except RegistryError as exc:
        print(f"registry error: {exc}", file=sys.stderr)
        sys.exit(EXIT_REGISTRY)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(EXIT_UNKNOWN)


if __name__ == "__main__":
    main()
