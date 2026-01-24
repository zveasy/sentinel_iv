import json
import os
import sys
import time
from argparse import ArgumentParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from hb import engine
from hb.config import load_metric_registry, load_compare_plan


def _load_metrics(path):
    with open(path, "r") as f:
        payload = json.load(f)
    metrics = {}
    for name, value in payload.items():
        metrics[name] = {"value": value, "unit": None, "tags": None}
    return metrics


def _synthetic_metrics(metric_names, offset=0.0):
    metrics = {}
    for idx, name in enumerate(metric_names):
        metrics[name] = {"value": float(idx) + offset, "unit": None, "tags": None}
    return metrics


def main():
    parser = ArgumentParser(description="Benchmark compare_metrics with and without ComparePlan.")
    parser.add_argument("--metric-registry", default="metric_registry.yaml")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--metrics", type=int, default=5000)
    parser.add_argument("--baseline-json", default=None, help="optional baseline metrics JSON")
    parser.add_argument("--current-json", default=None, help="optional current metrics JSON")
    args = parser.parse_args()

    registry = load_metric_registry(args.metric_registry)
    plan = load_compare_plan(args.metric_registry)

    metric_names = sorted(registry.get("metrics", {}).keys())[: args.metrics]
    if args.baseline_json and args.current_json:
        baseline = _load_metrics(args.baseline_json)
        current = _load_metrics(args.current_json)
    else:
        baseline = _synthetic_metrics(metric_names, offset=0.0)
        current = _synthetic_metrics(metric_names, offset=1.0)

    start = time.time()
    for _ in range(args.runs):
        engine.compare_metrics(current, baseline, registry, distribution_enabled=True, plan=None)
    legacy_s = time.time() - start

    start = time.time()
    for _ in range(args.runs):
        engine.compare_metrics(current, baseline, registry, distribution_enabled=True, plan=plan)
    plan_s = time.time() - start

    print(f"legacy: {legacy_s:.4f}s for {args.runs} runs")
    print(f"plan:   {plan_s:.4f}s for {args.runs} runs")


if __name__ == "__main__":
    main()
