import os

import pandas as pd

from hb.schema import load_schema


def _infer_delimiter(path, schema):
    delimiter = schema.get("delimiter")
    if delimiter:
        return delimiter
    _, ext = os.path.splitext(path.lower())
    if ext == ".tsv":
        return "\t"
    return ","


def _validate_columns(columns, schema):
    required = schema.get("required_columns", []) or []
    optional = schema.get("optional_columns", []) or []
    allow_extra = schema.get("allow_extra_columns", True)
    known = set(required) | set(optional)
    missing = [col for col in required if col not in columns]
    if missing:
        raise ValueError(f"SCHEMA_ERROR: missing required columns: {', '.join(missing)}")
    extras = [col for col in columns if col not in known]
    if extras and not allow_extra:
        raise ValueError(f"SCHEMA_ERROR: unknown columns: {', '.join(extras)}")
    if extras and allow_extra:
        print(f"schema warning: extra columns ignored: {', '.join(extras)}")
    return required, optional


def parse(path):
    schema_path = os.environ.get("HB_CUSTOM_SCHEMA_PATH")
    if not schema_path:
        raise ValueError("SCHEMA_ERROR: custom schema path not set")
    schema = load_schema(schema_path)
    delimiter = _infer_delimiter(path, schema)
    read_kwargs = {
        "dtype": str,
        "keep_default_na": False,
        "encoding_errors": "replace",
    }
    if delimiter == "whitespace":
        read_kwargs["sep"] = r"\s+"
        read_kwargs["engine"] = "python"
    else:
        read_kwargs["sep"] = delimiter
    try:
        df = pd.read_csv(path, **read_kwargs)
    except UnicodeDecodeError:
        read_kwargs["encoding"] = "latin1"
        df = pd.read_csv(path, **read_kwargs)
    if df.empty:
        raise ValueError("SCHEMA_ERROR: no rows found")

    required, _ = _validate_columns(df.columns.tolist(), schema)
    column_types = schema.get("column_types", {}) or {}

    invalid = []
    numeric_cols = []
    for col, col_type in column_types.items():
        if col not in df.columns:
            continue
        series = df[col].astype(str).str.strip()
        if col_type in ("int", "float"):
            numeric = pd.to_numeric(series.replace({"": None}), errors="coerce")
            if col in required and numeric.isna().any():
                invalid.append(col)
            df[col] = numeric
            numeric_cols.append(col)
        else:
            df[col] = series

    if invalid:
        raise ValueError(f"SCHEMA_ERROR: invalid values in columns: {', '.join(sorted(invalid))}")

    metrics = {}
    for col in numeric_cols:
        values = df[col].dropna()
        if values.empty:
            continue
        metrics[col] = {"value": float(values.mean()), "unit": None, "tags": None}

    if not metrics:
        raise ValueError("SCHEMA_ERROR: no numeric metrics available")
    return metrics
