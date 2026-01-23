import json
import os
import time
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, Optional

import pandas as pd
import yaml

from hb.schema import load_schema


@dataclass
class CompareResult:
    status: str
    run_id: str
    report_dir: str
    report_path: str
    summary_path: str
    baseline_run_id: Optional[str]
    drift_score: Optional[float]
    drivers: Optional[list]


def _ensure_dirs(path):
    os.makedirs(path, exist_ok=True)


def _default_run_meta(source, seed=None):
    seed = seed or {}
    return {
        "program": seed.get("program", "hb_compare"),
        "subsystem": seed.get("subsystem", source),
        "test_name": seed.get("test_name", "default"),
        "scenario_id": seed.get("scenario_id", "default"),
        "operating_mode": seed.get("operating_mode", "default"),
        "environment": seed.get("environment", "local"),
        "environment_fingerprint": seed.get("environment_fingerprint", "local"),
        "sensor_config_id": seed.get("sensor_config_id", "default"),
        "input_data_version": seed.get("input_data_version", "1"),
    }


def _write_run_meta(run_meta, out_dir, prefix):
    path = os.path.join(out_dir, "logs")
    _ensure_dirs(path)
    out_path = os.path.join(path, f"{prefix}_{uuid.uuid4().hex}.json")
    with open(out_path, "w") as f:
        json.dump(run_meta, f, indent=2)
    return out_path


def _detect_delimiter(sample_bytes):
    sample = sample_bytes.splitlines()[0] if sample_bytes else b""
    tab_count = sample.count(b"\t")
    comma_count = sample.count(b",")
    if tab_count > comma_count:
        return "\t"
    if comma_count > 0:
        return ","
    return "whitespace"


def _infer_column_types(df):
    types = {}
    for col in df.columns:
        series = df[col].astype(str).str.strip()
        non_empty = series[series != ""]
        if non_empty.empty:
            types[col] = "str"
            continue
        numeric = pd.to_numeric(non_empty, errors="coerce")
        if numeric.notna().all():
            if (numeric % 1 == 0).all():
                types[col] = "int"
            else:
                types[col] = "float"
        else:
            types[col] = "str"
    return types


def _build_schema_from_file(schema_name, sample_path, out_dir, require_all=False):
    with open(sample_path, "rb") as f:
        sample_bytes = f.read()
    delimiter = _detect_delimiter(sample_bytes)
    read_kwargs = {
        "dtype": str,
        "keep_default_na": False,
        "nrows": 500,
        "encoding_errors": "replace",
    }
    if delimiter == "whitespace":
        read_kwargs["sep"] = r"\s+"
        read_kwargs["engine"] = "python"
    else:
        read_kwargs["sep"] = delimiter
    try:
        df = pd.read_csv(BytesIO(sample_bytes), **read_kwargs)
    except UnicodeDecodeError:
        read_kwargs["encoding"] = "latin1"
        df = pd.read_csv(BytesIO(sample_bytes), **read_kwargs)
    if df.empty or not df.columns.tolist():
        raise ValueError("No header row detected in baseline file.")
    columns = df.columns.tolist()
    inferred_types = _infer_column_types(df)
    required = columns if require_all else []
    optional = [col for col in columns if col not in required]
    schema = {
        "name": schema_name,
        "format": "tabular",
        "delimiter": delimiter,
        "header": True,
        "required_columns": required,
        "optional_columns": optional,
        "column_types": inferred_types,
        "allow_extra_columns": True,
    }
    schema_dir = os.path.join(out_dir, "schemas")
    _ensure_dirs(schema_dir)
    schema_path = os.path.join(schema_dir, f"{schema_name}.yaml")
    with open(schema_path, "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False)
    return schema_path


def _build_custom_registry(schema_path, out_dir):
    registry_path = os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml")
    with open(registry_path, "r") as f:
        registry = yaml.safe_load(f) or {}
    metrics = registry.get("metrics", {})
    schema = load_schema(schema_path)
    column_types = schema.get("column_types", {}) or {}
    for col, col_type in column_types.items():
        if col_type not in ("int", "float"):
            continue
        if col in metrics:
            continue
        metrics[col] = {
            "aliases": [col],
            "drift_threshold": 0.1,
            "drift_percent": 10.0,
            "min_effect": 0.01,
            "source_columns": [col],
        }
    registry["metrics"] = metrics
    logs_dir = os.path.join(out_dir, "logs")
    _ensure_dirs(logs_dir)
    out_path = os.path.join(logs_dir, f"metric_registry_custom_{uuid.uuid4().hex}.yaml")
    with open(out_path, "w") as f:
        yaml.safe_dump(registry, f, sort_keys=False)
    return out_path


def _resolve_run_meta(run_meta, source, out_dir):
    baseline_meta = None
    current_meta = None
    if isinstance(run_meta, str):
        with open(run_meta, "r") as f:
            payload = json.load(f)
        run_meta = payload
    if isinstance(run_meta, dict):
        baseline_meta = run_meta.get("baseline")
        current_meta = run_meta.get("current")
        if baseline_meta is None and current_meta is None:
            baseline_meta = run_meta
            current_meta = run_meta

    if baseline_meta is None:
        baseline_meta = _default_run_meta(source)
    if current_meta is None:
        current_meta = _default_run_meta(source)

    baseline_meta_path = _write_run_meta(baseline_meta, out_dir, "baseline_meta")
    current_meta_path = _write_run_meta(current_meta, out_dir, "current_meta")
    return baseline_meta_path, current_meta_path


def _resolve_source(run_meta, schema_mode):
    source_override = None
    if isinstance(run_meta, dict):
        meta = run_meta.get("current") if "current" in run_meta else run_meta
        if isinstance(meta, dict):
            source_override = meta.get("source") or meta.get("toolchain", {}).get("source_system")
    if source_override:
        return source_override
    if schema_mode in ("auto", "file"):
        return "custom_tabular"
    return os.environ.get("HB_COMPARE_SOURCE", "pba_excel")


def run_compare(
    baseline_path,
    run_path,
    out_dir,
    schema_mode,
    schema_path,
    thresholds_path,
    run_meta=None,
):
    out_dir = os.path.abspath(out_dir)
    _ensure_dirs(out_dir)
    _ensure_dirs(os.path.join(out_dir, "runs"))
    _ensure_dirs(os.path.join(out_dir, "reports"))
    _ensure_dirs(os.path.join(out_dir, "logs"))

    source = _resolve_source(run_meta, schema_mode)
    baseline_meta_path, current_meta_path = _resolve_run_meta(run_meta, source, out_dir)

    baseline_policy = thresholds_path or os.environ.get("HB_BASELINE_POLICY", "baseline_policy.yaml")
    metric_registry = os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml")

    previous_schema = os.environ.get("HB_CUSTOM_SCHEMA_PATH")
    previous_registry = os.environ.get("HB_METRIC_REGISTRY")
    if source == "custom_tabular":
        if schema_mode == "auto":
            schema_name = f"auto_schema_{time.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
            schema_path = _build_schema_from_file(schema_name, baseline_path, out_dir)
        if not schema_path:
            raise ValueError("schema_path is required when schema_mode is 'file'")
        os.environ["HB_CUSTOM_SCHEMA_PATH"] = schema_path
        metric_registry = _build_custom_registry(schema_path, out_dir)
        os.environ["HB_METRIC_REGISTRY"] = metric_registry
    try:
        from hb import cli

        baseline_args = cli.argparse.Namespace(
            source=source,
            path=baseline_path,
            run_meta=baseline_meta_path,
            out=os.path.join(out_dir, "runs", "baseline"),
            stream=False,
            baseline_policy=baseline_policy,
            metric_registry=metric_registry,
            db=os.path.join(out_dir, "logs", "runs.db"),
            reports=os.path.join(out_dir, "reports"),
            top=5,
            pdf=False,
            encrypt_key=None,
            sign_key=None,
            redaction_policy=None,
        )
        cli.run(baseline_args)

        current_args = cli.argparse.Namespace(
            source=source,
            path=run_path,
            run_meta=current_meta_path,
            out=os.path.join(out_dir, "runs", "current"),
            stream=False,
            baseline_policy=baseline_policy,
            metric_registry=metric_registry,
            db=os.path.join(out_dir, "logs", "runs.db"),
            reports=os.path.join(out_dir, "reports"),
            top=5,
            pdf=False,
            encrypt_key=None,
            sign_key=None,
            redaction_policy=None,
        )
        report_dir = cli.run(current_args)
    finally:
        if previous_schema:
            os.environ["HB_CUSTOM_SCHEMA_PATH"] = previous_schema
        elif "HB_CUSTOM_SCHEMA_PATH" in os.environ:
            del os.environ["HB_CUSTOM_SCHEMA_PATH"]
        if previous_registry:
            os.environ["HB_METRIC_REGISTRY"] = previous_registry
        elif "HB_METRIC_REGISTRY" in os.environ:
            del os.environ["HB_METRIC_REGISTRY"]

    report_path = os.path.join(report_dir, "drift_report.json")
    with open(report_path, "r") as f:
        report = json.load(f)

    html_path = os.path.join(report_dir, "drift_report.html")
    summary_path = os.path.join(report_dir, "summary.json")
    summary_payload = {
        "status": report.get("status"),
        "run_id": report.get("run_id"),
        "baseline_run_id": report.get("baseline_run_id"),
        "report_path": html_path,
        "report_json_path": report_path,
    }
    with open(summary_path, "w") as f:
        json.dump(summary_payload, f, indent=2)

    decision_basis = report.get("decision_basis") or {}
    return CompareResult(
        status=report.get("status"),
        run_id=report.get("run_id"),
        report_dir=report_dir,
        report_path=html_path,
        summary_path=summary_path,
        baseline_run_id=report.get("baseline_run_id"),
        drift_score=decision_basis.get("drift_score"),
        drivers=(report.get("drift_attribution") or {}).get("top_drivers", []),
    )
