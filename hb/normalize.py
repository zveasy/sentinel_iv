"""
Normalize raw telemetry events using config/telemetry_schema.yaml.
Maps vendor names -> canonical metric; applies unit conversion (e.g. ms->s, W->kW).
"""
import os
from typing import Any

import yaml


def load_telemetry_schema(path: str | None = None) -> dict:
    if path is None:
        path = os.environ.get("HB_TELEMETRY_SCHEMA", "config/telemetry_schema.yaml")
    if not os.path.isfile(path):
        return {"version": "1.0", "field_mapping": {}, "sources": {}}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _canonical_name(schema: dict, raw_name: str) -> str | None:
    mapping = schema.get("field_mapping") or {}
    raw = (raw_name or "").strip()
    if not raw:
        return None
    # Direct key
    if raw in mapping:
        entry = mapping[raw]
        if isinstance(entry, dict):
            return entry.get("canonical") or raw
        return str(entry)
    # Case-insensitive
    for k, v in mapping.items():
        if k.strip().lower() == raw.lower():
            if isinstance(v, dict):
                return v.get("canonical") or k
            return str(v)
    return raw


def _unit_factor(schema: dict, metric: str, unit: str | None) -> float:
    if not unit:
        return 1.0
    mapping = schema.get("field_mapping") or {}
    entry = mapping.get(metric, mapping.get(unit))
    if isinstance(entry, dict) and "factor" in entry:
        return float(entry["factor"])
    # Optional unit_map in schema for unit -> factor
    return 1.0


def normalize_telemetry(raw_events: list[dict], schema: dict | None = None) -> list[dict]:
    """
    Normalize raw events to canonical metric names and units.
    Each input: {timestamp, metric, value, unit?}
    Output: list of {metric, value, unit, timestamp} with canonical names and converted units.
    """
    if schema is None:
        schema = load_telemetry_schema()
    out = []
    for ev in raw_events:
        raw_metric = ev.get("metric") or ev.get("name")
        if not raw_metric:
            continue
        canonical = _canonical_name(schema, str(raw_metric))
        if not canonical:
            continue
        try:
            value = ev.get("value")
            if value is not None and not isinstance(value, (int, float)):
                value = float(value)
        except (TypeError, ValueError):
            continue
        unit = ev.get("unit")
        factor = _unit_factor(schema, canonical, unit)
        if value is not None and factor != 1.0:
            value = value * factor
        out.append({
            "metric": canonical,
            "value": value,
            "unit": unit or "",
            "timestamp": ev.get("timestamp", ""),
        })
    return out


def aggregate_to_metrics(normalized_events: list[dict], strategy: str = "last") -> dict[str, dict]:
    """
    Aggregate normalized events to one value per metric.
    strategy: "last" (last value) or "mean" (average over events).
    Returns dict metric -> {value, unit, tags} for engine.normalize_metrics / write_metrics_csv.
    """
    by_metric: dict[str, list[tuple[float | None, str]]] = {}
    for ev in normalized_events:
        m = ev.get("metric")
        if not m:
            continue
        v = ev.get("value")
        u = ev.get("unit") or ""
        if m not in by_metric:
            by_metric[m] = []
        by_metric[m].append((v, u))
    result = {}
    for metric, pairs in by_metric.items():
        if not pairs:
            continue
        if strategy == "last":
            v, u = pairs[-1]
            result[metric] = {"value": v, "unit": u, "tags": ""}
        else:
            vals = [p[0] for p in pairs if p[0] is not None]
            u = pairs[-1][1] if pairs else ""
            result[metric] = {"value": sum(vals) / len(vals) if vals else None, "unit": u, "tags": ""}
    return result
