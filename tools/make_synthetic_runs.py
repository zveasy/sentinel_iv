#!/usr/bin/env python3
import argparse
import csv
import os
import random
import uuid
from datetime import datetime, timedelta, timezone


BASE_METRICS = [
    ("avg_latency_ms", 10.0, "ms"),
    ("max_latency_ms", 20.0, "ms"),
    ("reset_count", 0.0, ""),
    ("watchdog_triggers", 0.0, ""),
    ("error_code_frequency", 0.01, ""),
    ("missed_deadlines", 0.0, ""),
]


def write_metrics_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Baseline", "Current", "Delta", "Threshold", "Unit", "Status"])
        for metric, value, unit in rows:
            writer.writerow([metric, value, value, "", "", unit, ""])


def write_run_meta(path, run_id, program, subsystem, test_name, environment, start, end):
    payload = {
        "run_id": run_id,
        "program": program,
        "subsystem": subsystem,
        "test_name": test_name,
        "environment": environment,
        "build": {"git_sha": "synthetic", "build_id": run_id},
        "timestamps": {"start_utc": start.isoformat(), "end_utc": end.isoformat()},
        "toolchain": {"source_system": "pba_excel"},
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        import json

        json.dump(payload, f, indent=2)


def make_run_rows(noise_scale, drift=None, alias_map=None):
    rows = []
    for metric, base, unit in BASE_METRICS:
        noise = random.uniform(-noise_scale, noise_scale)
        value = base + noise
        if drift and metric in drift:
            value += drift[metric]
        if metric in ["reset_count", "watchdog_triggers", "missed_deadlines"]:
            value = max(0, round(value))
        output_metric = alias_map.get(metric, metric) if alias_map else metric
        rows.append((output_metric, round(value, 4), unit))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic baseline and drifted runs.")
    parser.add_argument("--out", default="samples/synthetic", help="output directory")
    parser.add_argument("--baseline-count", type=int, default=3)
    parser.add_argument("--drift-count", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--noise", type=float, default=0.2)
    parser.add_argument("--program", default="harmony")
    parser.add_argument("--subsystem", default="core")
    parser.add_argument("--test-name", default="synthetic_demo")
    parser.add_argument("--environment", default="lab")
    parser.add_argument("--schema-drift-baseline", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    base_dir = args.out
    start = datetime.now(timezone.utc)

    baseline_alias_map = None
    if args.schema_drift_baseline:
        baseline_alias_map = {
            "avg_latency_ms": "Avg Latency (ms)",
            "max_latency_ms": "Latency Max",
            "reset_count": "Resets",
            "watchdog_triggers": "Watchdog Count",
            "error_code_frequency": "error_rate",
            "missed_deadlines": "Deadline Misses",
        }

    for idx in range(args.baseline_count):
        run_id = f"baseline_{idx}_{uuid.uuid4().hex[:8]}"
        run_dir = os.path.join(base_dir, run_id)
        rows = make_run_rows(args.noise, alias_map=baseline_alias_map)
        write_metrics_csv(os.path.join(run_dir, "source.csv"), rows)
        write_run_meta(
            os.path.join(run_dir, "run_meta.json"),
            run_id,
            args.program,
            args.subsystem,
            args.test_name,
            args.environment,
            start + timedelta(minutes=idx),
            start + timedelta(minutes=idx, seconds=30),
        )

    drift_targets = [
        ("latency_tail", {"avg_latency_ms": 2.5, "max_latency_ms": 6.0}),
        ("error_rate", {"error_code_frequency": 0.06, "missed_deadlines": 1.0}),
        ("reset_event", {"reset_count": 1.0, "watchdog_triggers": 1.0}),
        (
            "schema_drift",
            {"avg_latency_ms": 2.5, "max_latency_ms": 6.0},
        ),
    ]

    alias_map = {
        "avg_latency_ms": "Avg Latency (ms)",
        "max_latency_ms": "Latency Max",
        "reset_count": "Resets",
        "watchdog_triggers": "Watchdog Count",
        "error_code_frequency": "error_rate",
        "missed_deadlines": "Deadline Misses",
    }

    for idx in range(args.drift_count):
        drift_type, drift = drift_targets[idx % len(drift_targets)]
        run_id = f"drift_{drift_type}_{idx}_{uuid.uuid4().hex[:8]}"
        run_dir = os.path.join(base_dir, run_id)
        if drift_type == "schema_drift":
            rows = make_run_rows(args.noise, drift=drift, alias_map=alias_map)
        else:
            rows = make_run_rows(args.noise, drift=drift)
        write_metrics_csv(os.path.join(run_dir, "source.csv"), rows)
        write_run_meta(
            os.path.join(run_dir, "run_meta.json"),
            run_id,
            args.program,
            args.subsystem,
            args.test_name,
            args.environment,
            start + timedelta(minutes=100 + idx),
            start + timedelta(minutes=100 + idx, seconds=30),
        )

    print(f"wrote synthetic runs to {base_dir}")


if __name__ == "__main__":
    main()
