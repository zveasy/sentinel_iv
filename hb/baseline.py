"""
Baseline training from time window: aggregate metrics from runs in last N hours, create versioned baseline.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

from hb.registry import (
    init_db,
    list_runs_since,
    fetch_metrics,
    upsert_run,
    replace_metrics,
    add_baseline_version,
    list_baseline_versions,
)
from hb.io import write_json, write_metrics_csv


def _parse_window(window: str) -> timedelta:
    """Parse '24h', '7d', '1h' -> timedelta."""
    w = (window or "").strip().lower()
    if not w:
        return timedelta(hours=24)
    if w.endswith("h"):
        return timedelta(hours=float(w[:-1]))
    if w.endswith("d"):
        return timedelta(days=float(w[:-1]))
    if w.endswith("m"):
        return timedelta(minutes=float(w[:-1]))
    return timedelta(hours=24)


def _aggregate_metrics(list_of_metrics: list[dict]) -> dict:
    """Aggregate: median per metric across runs. Each item is metric -> {value, unit, tags}."""
    by_metric = {}
    for run_metrics in list_of_metrics:
        for metric, data in run_metrics.items():
            v = data.get("value")
            if v is None:
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if metric not in by_metric:
                by_metric[metric] = []
            by_metric[metric].append((v, data.get("unit"), data.get("tags")))
    result = {}
    for metric, pairs in by_metric.items():
        vals = [p[0] for p in pairs]
        vals.sort()
        n = len(vals)
        if n % 2 == 1:
            med = vals[n // 2]
        else:
            med = (vals[n // 2 - 1] + vals[n // 2]) / 2.0
        unit = pairs[-1][1] if pairs else ""
        tags = pairs[-1][2] if pairs else ""
        result[metric] = {"value": med, "unit": unit, "tags": tags}
    return result


def create_baseline_from_window(
    db_path: str,
    window: str = "24h",
    registry_hash: str | None = None,
    out_dir: str | None = None,
) -> tuple[str, str]:
    """
    Create a baseline from runs in the last `window` (e.g. 24h, 7d).
    Returns (version_id, baseline_run_id).
    """
    conn = init_db(db_path)
    delta = _parse_window(window)
    since = (datetime.now(timezone.utc) - delta).isoformat()
    rows = list_runs_since(conn, since)
    if not rows:
        raise ValueError(f"No runs found since {since} (window={window})")
    run_ids = [r[0] for r in rows]
    all_metrics = []
    for run_id in run_ids:
        m = fetch_metrics(conn, run_id)
        if m:
            all_metrics.append(m)
    if not all_metrics:
        raise ValueError("No metrics in the selected runs")
    aggregated = _aggregate_metrics(all_metrics)
    version_id = f"v_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    baseline_run_id = f"baseline_{version_id}"

    run_meta = {
        "run_id": baseline_run_id,
        "program": None,
        "toolchain": {"source_system": "baseline_create"},
        "timestamps": {"start_utc": since, "end_utc": datetime.now(timezone.utc).isoformat()},
        "build": {},
    }
    upsert_run(conn, run_meta, "PASS", baseline_run_id=None, registry_hash=registry_hash)
    rows_metrics = [{"metric": m, "value": d["value"], "unit": d.get("unit"), "tags": d.get("tags")} for m, d in aggregated.items()]
    replace_metrics(conn, baseline_run_id, rows_metrics)
    add_baseline_version(conn, version_id, baseline_run_id, run_ids, signature=None)
    conn.close()

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        write_json(os.path.join(out_dir, "run_meta_normalized.json"), run_meta)
        write_metrics_csv(os.path.join(out_dir, "metrics_normalized.csv"), [{"metric": m, "value": d["value"], "unit": d.get("unit") or "", "tags": d.get("tags") or ""} for m, d in aggregated.items()])

    return version_id, baseline_run_id
