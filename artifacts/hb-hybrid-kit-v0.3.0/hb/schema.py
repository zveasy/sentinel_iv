import os

import yaml

from hb.registry_utils import normalize_alias


def load_schema(path):
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _default_schema_path(name):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "schemas", f"{name}.yaml"))

def _ingest_schema_path(name):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ingest", "schemas", f"{name}.yaml"))


def load_pba_schema():
    path = os.environ.get("HB_SCHEMA_PBA_EXCEL", _default_schema_path("pba_excel"))
    return load_schema(path)


def load_nasa_http_tsv_schema():
    path = os.environ.get("HB_SCHEMA_NASA_HTTP_TSV", _ingest_schema_path("nasa_http_tsv"))
    return load_schema(path)


def load_smap_msl_telemetry_schema():
    path = os.environ.get("HB_SCHEMA_SMAP_MSL_TELEMETRY", _ingest_schema_path("smap_msl_telemetry"))
    return load_schema(path)


def validate_pba_header(schema, header):
    required = schema.get("required_columns", [])
    optional = schema.get("optional_columns", [])
    allow_either = schema.get("either_current_or_value", True)
    allow_extra = schema.get("allow_extra_columns", True)
    aliases = schema.get("aliases", {}) or {}

    alias_map = {}
    for canonical, names in aliases.items():
        canonical_norm = normalize_alias(canonical)
        for name in names:
            alias_map[normalize_alias(name)] = canonical_norm

    col_map = {}
    unknown = []
    required_norm = {normalize_alias(name) for name in required}
    optional_norm = {normalize_alias(name) for name in optional}
    known_norm = required_norm | optional_norm
    for idx, name in enumerate(header):
        if not name:
            continue
        normalized = normalize_alias(str(name))
        canonical = alias_map.get(normalized, normalized)
        col_map[canonical] = idx
        if canonical not in known_norm:
            unknown.append(str(name))
    missing = []
    for column in required_norm:
        if column not in col_map:
            missing.append(column)
    if allow_either and "current" not in col_map and "value" not in col_map:
        missing.append("current|value")

    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"schema error: missing required columns: {missing_list}")
    if unknown and not allow_extra:
        unknown_list = ", ".join(unknown)
        raise ValueError(f"schema error: unknown columns: {unknown_list}")
    return col_map, unknown


def parse_numeric(value, column_name, row_number):
    if value is None or str(value).strip() == "":
        raise ValueError(f"schema error: missing numeric value in {column_name} at row {row_number}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"schema error: non-numeric value in {column_name} at row {row_number}") from exc
