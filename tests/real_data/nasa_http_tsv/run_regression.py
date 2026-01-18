#!/usr/bin/env python3
import argparse
import os
import sys

import pandas as pd
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from hb.adapters import nasa_http_tsv  # noqa: E402
from hb.cli import load_metric_registry  # noqa: E402
from hb.engine import compare_metrics, normalize_metrics  # noqa: E402


def _load_manifest(path):
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _resolve_root(raw_root):
    if not raw_root:
        return raw_root
    if raw_root.startswith("${") and raw_root.endswith("}"):
        key = raw_root[2:-1]
        if ":-" in key:
            var, default = key.split(":-", 1)
            return os.environ.get(var, default)
        return os.environ.get(key)
    return raw_root


def _load_events(files):
    frames = [nasa_http_tsv.load_events(path) for path in files]
    if not frames:
        raise ValueError("no rows loaded from dataset")
    return pd.concat(frames, ignore_index=True)


def _window_bounds(events, window):
    min_ts = int(events["ts"].min())
    max_ts = int(events["ts"].max())
    span = max_ts - min_ts
    if "start_ts" in window and "end_ts" in window:
        start = int(window["start_ts"])
        end = int(window["end_ts"])
    elif "start_pct" in window:
        start_pct = float(window["start_pct"])
        duration_pct = float(window.get("duration_pct", 0.01))
        start = int(min_ts + span * start_pct)
        end = int(start + span * duration_pct)
    elif "start_offset_seconds" in window:
        start = int(min_ts + window["start_offset_seconds"])
        end = int(start + window.get("duration_seconds", 0))
    else:
        raise ValueError("window missing bounds")
    if end < start:
        end = start
    if end > max_ts:
        end = max_ts
    if start < min_ts:
        start = min_ts
    return start, end


def main():
    parser = argparse.ArgumentParser(description="NASA HTTP TSV regression harness")
    parser.add_argument(
        "--manifest",
        default=os.path.join(os.path.dirname(__file__), "manifest.yaml"),
    )
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    dataset = manifest.get("dataset", {})
    root = _resolve_root(dataset.get("dataset_root"))
    if not root:
        print("NASA_HTTP_TSV_ROOT not set; export NASA_HTTP_TSV_ROOT to dataset root", file=sys.stderr)
        return 2

    file_names = dataset.get("files", [])
    files = [os.path.join(root, name) for name in file_names]
    missing = [path for path in files if not os.path.exists(path)]
    if missing:
        print("missing dataset files:", ", ".join(missing), file=sys.stderr)
        return 2

    try:
        events = _load_events(files)
    except ValueError as exc:
        print(f"FAIL schema validation: {exc}")
        return 2

    registry = load_metric_registry(os.path.join(ROOT_DIR, "metric_registry.yaml"))

    windows = manifest.get("windows", [])
    window_metrics = {}
    failures = 0

    for window in windows:
        name = window.get("name", "<unnamed>")
        try:
            start, end = _window_bounds(events, window)
        except ValueError as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
            continue
        subset = events[(events["ts"] >= start) & (events["ts"] <= end)]
        if subset.empty:
            print(f"FAIL {name}: no rows in window")
            failures += 1
            continue
        raw = nasa_http_tsv.metrics_from_events(subset)
        metrics, warnings = normalize_metrics(raw, registry)
        if warnings:
            print(f"WARN {name}: {'; '.join(warnings)}")
        if not metrics:
            print(f"FAIL {name}: no metrics produced")
            failures += 1
            continue
        window_metrics[name] = metrics
        print(f"OK {name}: metrics={len(metrics)}")

    for window in windows:
        name = window.get("name")
        expected = window.get("expected_status")
        baseline = window.get("baseline")
        if expected is None or baseline is None:
            continue
        current = window_metrics.get(name)
        baseline_metrics = window_metrics.get(baseline)
        if current is None or baseline_metrics is None:
            print(f"FAIL {name}: missing metrics for baseline {baseline}")
            failures += 1
            continue
        if name == baseline:
            status = "PASS"
        else:
            status, _, _, _, _, _, _ = compare_metrics(current, baseline_metrics, registry)
        if isinstance(expected, list):
            ok = status in expected
        else:
            ok = status == expected
        if not ok:
            print(f"FAIL {name}: status {status} != expected {expected}")
            failures += 1
        else:
            print(f"OK {name}: status {status}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
