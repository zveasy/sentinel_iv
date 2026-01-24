import csv
import json
import os

import pandas as pd

from hb.registry_utils import normalize_alias
from hb.schema import load_nasa_http_tsv_schema


def _collect_paths(path):
    if os.path.isdir(path):
        candidates = [
            os.path.join(path, name)
            for name in sorted(os.listdir(path))
            if name.lower().endswith(".tsv")
        ]
        if not candidates:
            raise ValueError(f"SCHEMA_ERROR: no .tsv files found in {path}")
        return candidates
    return [path]


def _profile_path_from_env(key):
    value = os.environ.get(key)
    if not value:
        return None
    if os.path.isdir(value):
        return os.path.join(value, "baseline_profile.json")
    return value


def _load_profile():
    path = _profile_path_from_env("HB_BASELINE_PROFILE_IN")
    if not path or not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def _save_profile(profile):
    path = _profile_path_from_env("HB_BASELINE_PROFILE_OUT")
    if not path:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)
    return path


def _open_tsv(path, encoding=None):
    try:
        return open(path, "r", encoding=encoding or "utf-8", errors="replace")
    except UnicodeDecodeError:
        return open(path, "r", encoding="latin1", errors="replace")


def _build_column_map(columns, schema):
    required = schema.get("required_columns", [])
    optional = schema.get("optional_columns", [])
    allow_extra = schema.get("allow_extra_columns", True)
    aliases = schema.get("aliases", {}) or {}

    alias_map = {}
    for canonical, names in aliases.items():
        canonical_norm = normalize_alias(canonical)
        for name in names:
            alias_map[normalize_alias(name)] = canonical_norm

    required_norm = {normalize_alias(name) for name in required}
    optional_norm = {normalize_alias(name) for name in optional}
    known_norm = required_norm | optional_norm

    col_map = {}
    extras = []
    for name in columns:
        if not name:
            continue
        normalized = normalize_alias(str(name))
        canonical = alias_map.get(normalized, normalized)
        col_map[canonical] = name
        if canonical not in known_norm:
            extras.append(str(name))

    missing = [name for name in required_norm if name not in col_map]
    if missing:
        raise ValueError(f"SCHEMA_ERROR: missing required columns: {', '.join(sorted(missing))}")
    if extras and not allow_extra:
        raise ValueError(f"SCHEMA_ERROR: unknown columns: {', '.join(extras)}")
    return col_map, extras, allow_extra


def _coerce_int(series, field, blank_zero=False):
    cleaned = series.astype(str).str.strip()
    if blank_zero:
        cleaned = cleaned.replace({"": "0", "-": "0"})
    numeric = pd.to_numeric(cleaned, errors="coerce")
    invalid = numeric.isna().any()
    if invalid:
        return None, True
    return numeric.astype(int), False


def _coerce_required_str(series, field):
    cleaned = series.astype(str).str.strip()
    invalid = (cleaned == "").any()
    if invalid:
        return None, True
    return cleaned, False


def _metrics_from_counts(total, error_count):
    error_rate = error_count / total if total else 0.0
    return {
        "http_error_rate": {
            "value": error_rate,
            "unit": None,
            "tags": None,
        }
    }


def load_events(path):
    schema = load_nasa_http_tsv_schema()
    frames = []
    for file_path in _collect_paths(path):
        try:
            df = pd.read_csv(file_path, sep="\t", dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            df = pd.read_csv(
                file_path,
                sep="\t",
                dtype=str,
                keep_default_na=False,
                encoding="latin1",
            )
        if df.empty:
            raise ValueError(f"SCHEMA_ERROR: no rows found in {file_path}")
        col_map, extras, allow_extra = _build_column_map(df.columns, schema)
        if extras and allow_extra:
            print(f"schema warning: extra columns ignored: {', '.join(extras)}")

        invalid_fields = set()
        host, invalid = _coerce_required_str(df[col_map["host"]], "host")
        if invalid:
            invalid_fields.add("host")
        method, invalid = _coerce_required_str(df[col_map["method"]], "method")
        if invalid:
            invalid_fields.add("method")
        path_col, invalid = _coerce_required_str(df[col_map["url"]], "url")
        if invalid:
            invalid_fields.add("url")

        ts, invalid = _coerce_int(df[col_map["time"]], "time")
        if invalid:
            invalid_fields.add("time")
        status_code, invalid = _coerce_int(df[col_map["response"]], "response")
        if invalid:
            invalid_fields.add("response")
        bytes_sent, invalid = _coerce_int(df[col_map["bytes"]], "bytes", blank_zero=True)
        if invalid:
            invalid_fields.add("bytes")

        if invalid_fields:
            raise ValueError(
                "SCHEMA_ERROR: invalid values in columns: " + ", ".join(sorted(invalid_fields))
            )

        frame = pd.DataFrame(
            {
                "ts": ts,
                "status_code": status_code,
                "method": method,
                "path": path_col,
                "bytes": bytes_sent,
            }
        )
        frames.append(frame)

    if not frames:
        raise ValueError("SCHEMA_ERROR: no rows found")
    return pd.concat(frames, ignore_index=True)


def metrics_from_events(events):
    if events.empty:
        raise ValueError("SCHEMA_ERROR: no rows found")
    total = len(events)
    error_count = int((events["status_code"] >= 400).sum())
    error_rate = error_count / total if total else 0.0
    return {
        "http_error_rate": {
            "value": error_rate,
            "unit": None,
            "tags": None,
        }
    }


def parse(path):
    events = load_events(path)
    return metrics_from_events(events)


def parse_stream(path):
    schema = load_nasa_http_tsv_schema()
    profile = _load_profile()
    delimiter = "\t"
    total = 0
    error_count = 0
    column_map = None

    for file_path in _collect_paths(path):
        with _open_tsv(file_path, encoding=(profile or {}).get("encoding")) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            if not reader.fieldnames:
                raise ValueError(f"SCHEMA_ERROR: no header row in {file_path}")
            if profile and profile.get("column_map"):
                column_map = profile["column_map"]
            if column_map is None:
                column_map, extras, allow_extra = _build_column_map(reader.fieldnames, schema)
                if extras and allow_extra:
                    print(f"schema warning: extra columns ignored: {', '.join(extras)}")
            missing = [key for key in ["host", "method", "url", "time", "response", "bytes"] if key not in column_map]
            if missing:
                raise ValueError(f"SCHEMA_ERROR: missing required columns: {', '.join(missing)}")
            for row in reader:
                total += 1
                try:
                    status_code = int(row[column_map["response"]])
                except (TypeError, ValueError):
                    raise ValueError("SCHEMA_ERROR: invalid response values")
                if status_code >= 400:
                    error_count += 1

    if total == 0:
        raise ValueError("SCHEMA_ERROR: no rows found")

    if profile is None:
        profile = {
            "schema_version": "1.0",
            "delimiter": delimiter,
            "encoding": "utf-8",
            "column_map": column_map,
            "total_rows": total,
            "error_count": error_count,
            "metric_ids": {"http_error_rate": 0},
            "metrics_summary": {"http_error_rate": {"count": total, "mean": error_count / total}},
        }
        _save_profile(profile)

    return _metrics_from_counts(total, error_count)
