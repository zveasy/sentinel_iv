#!/usr/bin/env python3
import argparse
import ast
import os
import sys

import pandas as pd
import yaml


def _parse_sequences(raw):
    if raw is None or str(raw).strip() == "":
        return []
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    sequences = []
    for entry in value:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        start, end = entry
        try:
            start = int(start)
            end = int(end)
        except (TypeError, ValueError):
            continue
        if end < start:
            start, end = end, start
        sequences.append([start, end])
    return sequences


def _select_anomalies(sequences):
    if not sequences:
        return None, None
    first = sequences[0]
    last = sequences[-1]
    return first, last


def _baseline_window(first_range):
    if not first_range:
        return [0, 0]
    start = 0
    end = max(0, int(first_range[0]) - 1)
    if end < start:
        end = start
    return [start, end]


def main():
    parser = argparse.ArgumentParser(description="Generate SMAP/MSL manifest windows")
    parser.add_argument(
        "--root",
        default=os.environ.get("SMAP_MSL_ROOT", "/Users/zakariyaveasy/Downloads/labeled_anomalies"),
    )
    parser.add_argument(
        "--output",
        default=os.path.join("tests", "real_data", "smap_msl", "manifest.yaml"),
    )
    args = parser.parse_args()

    csv_path = os.path.join(args.root, "labeled_anomalies.csv")
    if not os.path.exists(csv_path):
        print(f"missing labeled_anomalies.csv at {csv_path}", file=sys.stderr)
        return 2

    df = pd.read_csv(csv_path)
    if df.empty:
        print("labeled_anomalies.csv is empty", file=sys.stderr)
        return 2

    windows = []
    for _, row in df.iterrows():
        chan_id = str(row.get("chan_id", "")).strip()
        spacecraft = str(row.get("spacecraft", "")).strip()
        sequences = _parse_sequences(row.get("anomaly_sequences"))
        if not chan_id or not spacecraft or not sequences:
            continue
        first_range, last_range = _select_anomalies(sequences)
        if not first_range:
            continue
        baseline_range = _baseline_window(first_range)

        baseline_name = f"{spacecraft}_{chan_id}_baseline"
        mid_name = f"{spacecraft}_{chan_id}_mid"
        late_name = f"{spacecraft}_{chan_id}_late"

        windows.append(
            {
                "name": baseline_name,
                "spacecraft": spacecraft,
                "chan_id": chan_id,
                "split": "test",
                "start_index": baseline_range[0],
                "end_index": baseline_range[1],
                "baseline": baseline_name,
                "expected_status": "PASS",
            }
        )
        windows.append(
            {
                "name": mid_name,
                "spacecraft": spacecraft,
                "chan_id": chan_id,
                "split": "test",
                "start_index": int(first_range[0]),
                "end_index": int(first_range[1]),
                "baseline": baseline_name,
                "expected_status": "PASS_WITH_DRIFT",
            }
        )
        windows.append(
            {
                "name": late_name,
                "spacecraft": spacecraft,
                "chan_id": chan_id,
                "split": "test",
                "start_index": int(last_range[0]),
                "end_index": int(last_range[1]),
                "baseline": baseline_name,
                "expected_status": "PASS_WITH_DRIFT",
            }
        )

    payload = {
        "dataset": {
            "dataset_root": "${SMAP_MSL_ROOT:-/Users/zakariyaveasy/Downloads/labeled_anomalies}",
            "anomalies_csv": "labeled_anomalies.csv",
        },
        "windows": windows,
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        yaml.safe_dump(payload, f, sort_keys=False)

    print(f"wrote {args.output} windows={len(windows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
