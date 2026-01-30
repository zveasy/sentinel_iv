#!/usr/bin/env python3
import argparse
import json
import sys
import yaml


def _load_limits(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f) or {}
    return payload.get("limits", {})


def main():
    parser = argparse.ArgumentParser(description="Check perf.json against limits")
    parser.add_argument("--perf", required=True, help="path to perf.json")
    parser.add_argument("--limits", default="configs/perf_limits.yaml")
    args = parser.parse_args()

    with open(args.perf, "r") as f:
        perf = json.load(f)
    limits = _load_limits(args.limits)

    spans = perf.get("spans", [])
    meta = perf.get("meta", {})
    span_map = {item.get("name"): item.get("duration_s") for item in spans}

    issues = []
    total = sum(item.get("duration_s", 0) for item in spans)
    if limits.get("total_s") is not None and total > limits["total_s"]:
        issues.append(f"total_s {total:.3f} exceeds {limits['total_s']}")
    for key, limit in limits.items():
        if not key.endswith("_s") or key == "total_s":
            continue
        span_name = key.replace("_s", "")
        duration = span_map.get(span_name)
        if duration is not None and duration > limit:
            issues.append(f"{span_name} {duration:.3f}s exceeds {limit}s")

    metrics_bytes_max = limits.get("metrics_bytes_max")
    metrics_bytes = meta.get("metrics_bytes")
    if metrics_bytes_max is not None and metrics_bytes is not None and metrics_bytes > metrics_bytes_max:
        issues.append(f"metrics_bytes {metrics_bytes} exceeds {metrics_bytes_max}")

    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        sys.exit(1)
    print("PASS: perf within limits")
    sys.exit(0)


if __name__ == "__main__":
    main()
