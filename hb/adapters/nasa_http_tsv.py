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
