"""
Fault injectors: modify a stream or file to induce drift (for demos without hardware).
"""
import csv
import json
import random
from typing import Iterator


def value_corruption(rows: list[dict], noise_scale: float = 0.1, offset: float = 0.0) -> list[dict]:
    """Add noise or offset to numeric values. rows: list of {metric, value, ...}."""
    out = []
    for row in list(rows):
        r = dict(row)
        v = r.get("value")
        if v is not None:
            try:
                num = float(v)
                if noise_scale:
                    num += random.gauss(0, noise_scale * max(abs(num), 1e-6))
                if offset:
                    num += offset
                r["value"] = num
            except (TypeError, ValueError):
                pass
        out.append(r)
    return out


def schema_change(rows: list[dict], rename: dict | None = None, drop: list | None = None) -> list[dict]:
    """Rename or drop metrics. rename: {old_name: new_name}, drop: [metric_name, ...]."""
    rename = rename or {}
    drop = set(drop or [])
    out = []
    for row in list(rows):
        r = dict(row)
        m = r.get("metric")
        if m in drop:
            continue
        r["metric"] = rename.get(m, m)
        out.append(r)
    return out


def time_skew(rows: list[dict], skew_seconds: float = 0.0) -> list[dict]:
    """Apply time skew to timestamp field (for late/out-of-order simulation)."""
    out = []
    for row in list(rows):
        r = dict(row)
        ts = r.get("timestamp") or r.get("ts")
        if ts and skew_seconds:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                from datetime import timedelta
                r["timestamp"] = (dt + timedelta(seconds=skew_seconds)).isoformat()
            except Exception:
                pass
        out.append(r)
    return out


def stuck_at(rows: list[dict], metric: str, value: float) -> list[dict]:
    """Force one metric to a fixed value (stuck-at fault)."""
    out = []
    for row in list(rows):
        r = dict(row)
        if r.get("metric") == metric:
            r["value"] = value
        out.append(r)
    return out


def spike(rows: list[dict], metric: str, scale: float = 2.0, one_shot: bool = True) -> list[dict]:
    """Inject a single spike (or repeated) on one metric. scale multiplies the value once (or every row if not one_shot)."""
    out = []
    applied = False
    for row in list(rows):
        r = dict(row)
        if r.get("metric") == metric:
            try:
                v = float(r.get("value", 0))
                if one_shot and not applied:
                    r["value"] = v * scale
                    applied = True
                elif not one_shot:
                    r["value"] = v * scale
            except (TypeError, ValueError):
                pass
        out.append(r)
    return out


def sensor_drift(rows: list[dict], metric: str, drift_per_row: float = 0.01) -> list[dict]:
    """Simulate linear sensor drift: add cumulative offset per row for one metric."""
    cumulative = 0.0
    out = []
    for row in list(rows):
        r = dict(row)
        if r.get("metric") == metric:
            try:
                v = float(r.get("value", 0))
                r["value"] = v + cumulative
                cumulative += drift_per_row
            except (TypeError, ValueError):
                pass
        out.append(r)
    return out


def duplication(rows: list[dict], metric: str, count: int = 2) -> list[dict]:
    """Duplicate every row for one metric (count times), e.g. for duplicate-telemetry tests."""
    out = []
    for row in list(rows):
        r = dict(row)
        if r.get("metric") == metric:
            for _ in range(max(1, count)):
                out.append(dict(r))
        else:
            out.append(r)
    return out


def apply_to_csv(path_in: str, path_out: str, fault: str, **params) -> None:
    """Read CSV, apply fault, write CSV. fault: value_corruption, schema_change."""
    rows = []
    with open(path_in, "r", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if fault == "value_corruption":
        rows = value_corruption(rows, noise_scale=float(params.get("noise_scale", 0.1)), offset=float(params.get("offset", 0)))
    elif fault == "schema_change":
        rename = params.get("rename") or {}
        drop = params.get("drop") or []
        rows = schema_change(rows, rename=rename, drop=drop)
    elif fault == "time_skew":
        rows = time_skew(rows, skew_seconds=float(params.get("skew_seconds", 0)))
    elif fault == "stuck_at":
        rows = stuck_at(rows, metric=str(params.get("metric", "")), value=float(params.get("value", 0)))
    elif fault == "spike":
        rows = spike(rows, metric=str(params.get("metric", "")), scale=float(params.get("scale", 2.0)), one_shot=params.get("one_shot", True))
    elif fault == "sensor_drift":
        rows = sensor_drift(rows, metric=str(params.get("metric", "")), drift_per_row=float(params.get("drift_per_row", 0.01)))
    elif fault == "duplication":
        rows = duplication(rows, metric=str(params.get("metric", "")), count=int(params.get("count", 2)))
    with open(path_out, "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        else:
            f.write("metric,value,unit,tags\n")
