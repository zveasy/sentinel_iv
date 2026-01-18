#!/usr/bin/env python3
import argparse
import os
import sys

import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from hb.cli import load_metric_registry  # noqa: E402
from hb.engine import compare_metrics, normalize_metrics  # noqa: E402
from ingest.parsers import smap_msl_telemetry  # noqa: E402


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


def _slice_series(series, start_index, end_index):
    return series[(series["index"] >= start_index) & (series["index"] <= end_index)]


def main():
    parser = argparse.ArgumentParser(description="SMAP/MSL regression harness")
    parser.add_argument(
        "--manifest",
        default=os.path.join(os.path.dirname(__file__), "manifest.yaml"),
    )
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    dataset = manifest.get("dataset", {})
    root = _resolve_root(dataset.get("dataset_root"))
    if not root:
        print("SMAP_MSL_ROOT not set; export SMAP_MSL_ROOT to dataset root", file=sys.stderr)
        return 2

    registry = load_metric_registry(os.path.join(ROOT_DIR, "metric_registry.yaml"))
    windows = manifest.get("windows", [])
    if not windows:
        print("no windows defined in manifest", file=sys.stderr)
        return 2

    window_metrics = {}
    failures = 0
    metrics_ok = 0
    metrics_fail = 0
    status_ok = 0
    status_fail = 0

    for window in windows:
        name = window.get("name", "<unnamed>")
        spacecraft = window.get("spacecraft")
        chan_id = window.get("chan_id")
        start_index = window.get("start_index")
        end_index = window.get("end_index")
        split = window.get("split", "test")
        if not spacecraft or not chan_id:
            print(f"FAIL {name}: missing spacecraft/chan_id")
            failures += 1
            metrics_fail += 1
            continue
        try:
            series = smap_msl_telemetry.load_series(root, spacecraft, chan_id, split=split)
        except ValueError as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
            metrics_fail += 1
            continue
        subset = _slice_series(series, int(start_index), int(end_index))
        if subset.empty:
            print(f"FAIL {name}: no rows in window")
            failures += 1
            metrics_fail += 1
            continue
        raw = smap_msl_telemetry.metrics_from_series(subset)
        metrics, warnings = normalize_metrics(raw, registry)
        if warnings:
            print(f"WARN {name}: {'; '.join(warnings)}")
        if not metrics:
            print(f"FAIL {name}: no metrics produced")
            failures += 1
            metrics_fail += 1
            continue
        window_metrics[name] = metrics
        metrics_ok += 1
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
            status_fail += 1
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
            status_fail += 1
        else:
            print(f"OK {name}: status {status}")
            status_ok += 1

    print(
        "Summary: "
        f"metrics_ok={metrics_ok} metrics_fail={metrics_fail} "
        f"status_ok={status_ok} status_fail={status_fail}"
    )
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
