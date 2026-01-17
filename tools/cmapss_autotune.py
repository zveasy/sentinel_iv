#!/usr/bin/env python3
import argparse
import math
import os
import sys
from datetime import datetime, timezone

import yaml


def _load_rows(path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(stripped.split())
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


def _percentile(values, percentile):
    if not values:
        return None
    values = sorted(values)
    idx = int(round((len(values) - 1) * percentile))
    idx = max(0, min(idx, len(values) - 1))
    return values[idx]


def main():
    parser = argparse.ArgumentParser(description="Auto-tune CMAPSS thresholds from drift scores")
    parser.add_argument("--variant", default="fd003")
    parser.add_argument("--engine", type=int, default=1)
    parser.add_argument("--window", nargs=2, type=int, default=[150, 200])
    parser.add_argument("--p", type=float, default=0.70)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--root", default=os.environ.get("CMAPSS_ROOT", ""))
    parser.add_argument("--thresholds", default=None)
    args = parser.parse_args()

    if not args.root:
        print("CMAPSS_ROOT not set; export CMAPSS_ROOT to dataset root", file=sys.stderr)
        return 2

    variant = args.variant.lower()
    train_file = os.path.join(args.root, f"train_{variant.upper()}.txt")
    if not os.path.exists(train_file):
        print(f"missing dataset file: {train_file}", file=sys.stderr)
        return 2

    rows = _load_rows(train_file)
    baseline_rows = _slice_window(rows, args.engine, 1, 50)
    target_rows = _slice_window(rows, args.engine, args.window[0], args.window[1])

    if not baseline_rows or not target_rows:
        print("no rows found for baseline or target window", file=sys.stderr)
        return 2

    baseline_mean, baseline_std = _window_stats(baseline_rows)
    scores = [_cycle_score(row, baseline_mean, baseline_std) for row in target_rows]
    fail_threshold = _percentile(scores, args.p)
    if fail_threshold is None:
        print("unable to compute percentile", file=sys.stderr)
        return 2

    print(f"variant: {variant}")
    print(f"engine: {args.engine}")
    print(f"window: {args.window[0]}-{args.window[1]}")
    print(f"percentile: {args.p}")
    print(f"recommended fail_threshold: {fail_threshold:.3f}")

    if not args.write:
        print("dry-run: add --write to update thresholds file")
        return 0

    thresholds_path = args.thresholds
    if thresholds_path is None:
        thresholds_path = os.path.join("configs", f"cmapss_{variant}_thresholds.yaml")

    if os.path.exists(thresholds_path):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = thresholds_path + f".bak.{ts}"
        os.rename(thresholds_path, backup)
        print(f"backup written: {backup}")

    payload = {
        "variant": variant,
        "purpose": "regression_calibration_only",
        "warn_threshold": 3.0,
        "fail_threshold": round(float(fail_threshold), 3),
        "fail_persistence_cycles": 8,
        "notes": "Auto-tuned from CMAPSS drift score percentile; regression calibration only.",
    }
    with open(thresholds_path, "w") as f:
        yaml.safe_dump(payload, f, sort_keys=False)
    print(f"updated thresholds: {thresholds_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
