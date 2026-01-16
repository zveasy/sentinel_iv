#!/usr/bin/env python3
import argparse
import os
import random

import openpyxl


def main():
    parser = argparse.ArgumentParser(description="Generate a large XLSX for streaming stress tests.")
    parser.add_argument("--out", default="samples/large/large_pba.xlsx")
    parser.add_argument("--rows", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    random.seed(args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Data")
    ws.append(["Metric", "Current", "Unit"])

    metrics = [
        ("avg_latency_ms", "ms"),
        ("max_latency_ms", "ms"),
        ("reset_count", ""),
        ("watchdog_triggers", ""),
        ("error_code_frequency", ""),
        ("missed_deadlines", ""),
    ]

    for _ in range(args.rows):
        metric, unit = random.choice(metrics)
        if metric in ["reset_count", "watchdog_triggers", "missed_deadlines"]:
            value = random.randint(0, 1)
        elif metric == "error_code_frequency":
            value = round(random.uniform(0.0, 0.1), 4)
        elif metric == "avg_latency_ms":
            value = round(random.uniform(8.0, 16.0), 2)
        else:
            value = round(random.uniform(18.0, 30.0), 2)
        ws.append([metric, value, unit])

    wb.save(args.out)
    print(f"wrote {args.rows} rows to {args.out}")


if __name__ == "__main__":
    main()
