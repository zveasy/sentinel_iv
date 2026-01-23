import os

import numpy as np
import pandas as pd

from hb.registry_utils import normalize_alias
from hb.schema import load_smap_msl_telemetry_schema


class TelemetrySchemaError(ValueError):
    pass


def _base_data_dir(root):
    data_dir = os.path.join(root, "data")
    nested = os.path.join(data_dir, "data")
    if os.path.isdir(nested):
        return nested
    return data_dir


def _find_candidate_files(root, chan_id, split=None):
    data_dir = _base_data_dir(root)
    if not os.path.isdir(data_dir):
        raise TelemetrySchemaError(f"SCHEMA_ERROR: missing data directory: {data_dir}")

    chan_lower = chan_id.lower()
    preferred_names = {f"{chan_id}.npy", f"{chan_id}.csv"}
    preferred_lower = {name.lower() for name in preferred_names}

    matches = []
    preferred_dirs = []
    if split:
        preferred_dirs.append(os.path.join(data_dir, split))
    preferred_dirs.extend([os.path.join(data_dir, "test"), os.path.join(data_dir, "train")])

    for idx, directory in enumerate(preferred_dirs):
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            lower = name.lower()
            if lower in preferred_lower:
                matches.append(os.path.join(directory, name))
        if matches and split and idx == 0:
            return sorted(set(matches))

    if matches:
        return sorted(set(matches))

    for root_dir, _, files in os.walk(data_dir):
        for name in files:
            lower = name.lower()
            if not lower.endswith((".npy", ".csv")):
                continue
            if chan_lower in lower:
                matches.append(os.path.join(root_dir, name))

    return sorted(set(matches))


def resolve_channel_path(root, spacecraft, chan_id, split=None):
    matches = _find_candidate_files(root, chan_id, split=split)
    if not matches:
        raise TelemetrySchemaError(
            f"SCHEMA_ERROR: no telemetry file found for {spacecraft} {chan_id} under {root}"
        )
    if len(matches) > 1:
        print(
            "schema warning: multiple telemetry matches for"
            f" {spacecraft} {chan_id}; using {os.path.basename(matches[0])}"
        )
    return matches[0]


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
        raise TelemetrySchemaError(
            f"SCHEMA_ERROR: missing required columns: {', '.join(sorted(missing))}"
        )

    if "index" not in col_map and "timestamp" not in col_map:
        raise TelemetrySchemaError("SCHEMA_ERROR: missing required columns: index|timestamp")

    if extras and not allow_extra:
        raise TelemetrySchemaError(f"SCHEMA_ERROR: unknown columns: {', '.join(extras)}")

    return col_map, extras, allow_extra


def _coerce_numeric(series, field):
    numeric = pd.to_numeric(series, errors="coerce")
    invalid = numeric.isna().any()
    if invalid:
        return None, True
    return numeric, False


def load_series_from_path(path):
    schema = load_smap_msl_telemetry_schema()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".npy":
        values = np.load(path, allow_pickle=False)
        values = np.asarray(values).reshape(-1)
        if values.size == 0:
            raise TelemetrySchemaError(f"SCHEMA_ERROR: no rows found in {path}")
        series = pd.DataFrame({"index": range(len(values)), "value": values.astype(float)})
        return series

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.empty:
        raise TelemetrySchemaError(f"SCHEMA_ERROR: no rows found in {path}")

    col_map, extras, allow_extra = _build_column_map(df.columns, schema)
    if extras and allow_extra:
        print(f"schema warning: extra columns ignored: {', '.join(extras)}")

    value_col = col_map["value"]
    values, invalid = _coerce_numeric(df[value_col], "value")
    if invalid:
        raise TelemetrySchemaError("SCHEMA_ERROR: invalid values in columns: value")

    if "index" in col_map:
        index_values, invalid = _coerce_numeric(df[col_map["index"]], "index")
        if invalid:
            raise TelemetrySchemaError("SCHEMA_ERROR: invalid values in columns: index")
        indices = index_values.astype(int)
    else:
        indices = pd.Series(range(len(df)), dtype=int)

    series = pd.DataFrame({"index": indices, "value": values.astype(float)})
    return series


def load_series(root, spacecraft, chan_id, split=None):
    path = resolve_channel_path(root, spacecraft, chan_id, split=split)
    return load_series_from_path(path)


def metrics_from_series(series, sample_size=1000):
    if series.empty:
        raise TelemetrySchemaError("SCHEMA_ERROR: no rows found")
    values = series["value"].astype(float)
    mean = float(values.mean())
    std = float(values.std(ddof=0))

    if len(values) > sample_size:
        samples = values.sample(n=sample_size, random_state=0).tolist()
    else:
        samples = values.tolist()

    return {
        "smap_msl_mean": {"value": mean, "unit": None, "tags": None},
        "smap_msl_std": {"value": std, "unit": None, "tags": None},
        "smap_msl_value_dist": {
            "value": mean,
            "unit": None,
            "tags": {"samples": samples},
        },
    }


def parse(root, spacecraft, chan_id, start_index=None, end_index=None, split=None):
    series = load_series(root, spacecraft, chan_id, split=split)
    if start_index is not None or end_index is not None:
        if start_index is None:
            start_index = int(series["index"].min())
        if end_index is None:
            end_index = int(series["index"].max())
        subset = series[(series["index"] >= start_index) & (series["index"] <= end_index)]
    else:
        subset = series
    return metrics_from_series(subset)
