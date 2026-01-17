#!/usr/bin/env python3
import argparse
import math
import os
import sys
import tempfile

import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from hb.adapters import cmapss_fd004  # noqa: E402
from hb.cli import load_metric_registry  # noqa: E402
from hb.engine import normalize_metrics  # noqa: E402


def _load_manifest(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _resolve_root(raw_root):
    if raw_root and raw_root.startswith("${") and raw_root.endswith("}"):
        key = raw_root[2:-1]
        return os.environ.get(key)
    return raw_root


def _load_cmapss_rows(path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            rows.append(parts)
    return rows


def _slice_window(rows, engine_id, start_cycle, end_cycle):
    sliced = []
    for parts in rows:
        if len(parts) < 2:
            continue
        if int(parts[0]) != engine_id:
            continue
        cycle = int(parts[1])
        if cycle < start_cycle or cycle > end_cycle:
            continue
        sliced.append(parts)
    return sliced


def _window_stats(rows):
    sensor_values = []
    for row in rows:
        values = [float(value) for value in row[5:]]
        sensor_values.extend(values)
    mean = sum(sensor_values) / len(sensor_values)
    variance = sum((value - mean) ** 2 for value in sensor_values) / len(sensor_values)
    return mean, math.sqrt(variance)


def _cycle_score(row, baseline_mean, baseline_std):
    values = [float(value) for value in row[5:]]
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(variance)
    mean_pct = abs((mean - baseline_mean) / baseline_mean) * 100
    std_pct = abs((std - baseline_std) / baseline_std) * 100
    return (mean_pct + std_pct) * 100


def _score_window(rows, baseline_mean, baseline_std, warn_threshold, fail_threshold, persistence_cycles):
    scores = [_cycle_score(row, baseline_mean, baseline_std) for row in rows]
    max_streak = 0
    current = 0
    for score in scores:
        if score >= fail_threshold:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    if max_streak >= persistence_cycles:
        return "FAIL"
    if any(score >= warn_threshold for score in scores):
        return "PASS_WITH_DRIFT"
    return "PASS"


def _write_temp_window(rows):
    fd, path = tempfile.mkstemp(prefix="cmapss_window_", suffix=".txt")
    with os.fdopen(fd, "w") as f:
        for row in rows:
            f.write(" ".join(row) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description="CMAPSS FD004 regression harness")
    parser.add_argument(
        "--manifest",
        default=os.path.join(os.path.dirname(__file__), "manifest.yaml"),
    )
    parser.add_argument(
        "--thresholds",
        default=os.path.join(ROOT_DIR, "configs", "cmapss_fd001_thresholds.yaml"),
    )
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    with open(args.thresholds, "r") as f:
        thresholds = yaml.safe_load(f) or {}
    warn_threshold = float(thresholds.get("warn_threshold", 3.0))
    fail_threshold = float(thresholds.get("fail_threshold", 6.0))
    persistence_cycles = int(thresholds.get("fail_persistence_cycles", 10))

    dataset = manifest.get("dataset", {})
    root = _resolve_root(dataset.get("dataset_root"))
    if not root:
        print("CMAPSS_ROOT not set; export CMAPSS_ROOT to dataset root", file=sys.stderr)
        return 2

    train_file = os.path.join(root, dataset.get("files", {}).get("train", "train_FD004.txt"))
    if not os.path.exists(train_file):
        print(f"missing dataset file: {train_file}", file=sys.stderr)
        return 2

    rows = _load_cmapss_rows(train_file)
    if not rows:
        print("no rows loaded from dataset", file=sys.stderr)
        return 2

    registry = load_metric_registry(os.path.join(ROOT_DIR, "metric_registry.yaml"))

    windows = manifest.get("windows", [])
    window_metrics = {}
    window_rows = {}
    failures = 0
    for window in windows:
        engine_id = int(window["engine_id"])
        start_cycle = int(window["start_cycle"])
        end_cycle = int(window["end_cycle"])
        sliced = _slice_window(rows, engine_id, start_cycle, end_cycle)
        window_rows[window["name"]] = sliced
        if not sliced:
            print(f"FAIL {window['name']}: no rows in window")
            failures += 1
            continue
        temp_path = _write_temp_window(sliced)
        try:
            raw = cmapss_fd004.parse(temp_path)
            metrics, _ = normalize_metrics(raw, registry)
        except ValueError as exc:
            print(f"FAIL {window['name']}: {exc}")
            failures += 1
            continue
        finally:
            os.unlink(temp_path)
        if not metrics:
            print(f"FAIL {window['name']}: no metrics produced")
            failures += 1
        else:
            window_metrics[window["name"]] = metrics
            print(f"OK {window['name']}: metrics={len(metrics)}")

    for window in windows:
        expected = window.get("expected_status")
        baseline_name = window.get("baseline")
        if expected is None or baseline_name is None:
            continue
        current_metrics = window_metrics.get(window["name"])
        baseline_metrics = window_metrics.get(baseline_name)
        baseline_rows = window_rows.get(baseline_name)
        current_rows = window_rows.get(window["name"])
        if current_metrics is None or baseline_metrics is None:
            print(f"FAIL {window['name']}: missing metrics for baseline {baseline_name}")
            failures += 1
            continue
        if not baseline_rows or not current_rows:
            print(f"FAIL {window['name']}: missing rows for baseline {baseline_name}")
            failures += 1
            continue
        if window["name"] == baseline_name:
            status = "PASS"
        else:
            baseline_mean, baseline_std = _window_stats(baseline_rows)
            status = _score_window(
                current_rows,
                baseline_mean,
                baseline_std,
                warn_threshold,
                fail_threshold,
                persistence_cycles,
            )
        if isinstance(expected, list):
            ok = status in expected
        else:
            ok = status == expected
        if not ok:
            print(f"FAIL {window['name']}: status {status} != expected {expected}")
            failures += 1
        else:
            print(f"OK {window['name']}: status {status}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
