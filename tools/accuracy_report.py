#!/usr/bin/env python3
"""
Operator trust: accuracy report from feedback log.
Produces: "accuracy this month," "top noisy metrics," optional "recommended tuning" (threshold calibration suggestions).

Usage:
  python tools/accuracy_report.py [--feedback-log ~/.hb/feedback/feedback_log.jsonl] [--out report.json]
  bin/hb feedback export --output - --mode raw | python tools/accuracy_report.py --stdin
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_feedback(path: str | None, stdin: bool = False) -> list[dict]:
    if stdin:
        lines = sys.stdin.readlines()
        return [json.loads(l) for l in lines if l.strip()]
    if not path or not Path(path).exists():
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    ap = argparse.ArgumentParser(description="Accuracy report from feedback log")
    ap.add_argument("--feedback-log", default=None, help="Path to feedback_log.jsonl")
    ap.add_argument("--stdin", action="store_true", help="Read JSONL from stdin")
    ap.add_argument("--out", default=None, help="Write report JSON here")
    args = ap.parse_args()
    default_log = Path.home() / ".hb" / "feedback" / "feedback_log.jsonl"
    path = args.feedback_log or str(default_log)
    records = load_feedback(path, args.stdin)
    correct = sum(1 for r in records if r.get("verdict") == "Correct")
    too_sensitive = sum(1 for r in records if r.get("verdict") == "Too Sensitive")
    missed = sum(1 for r in records if r.get("verdict") == "Missed Severity")
    total = len(records)
    accuracy_pct = (correct / total * 100) if total else 0
    by_metric = defaultdict(lambda: {"correct": 0, "too_sensitive": 0, "missed": 0})
    for r in records:
        m = r.get("metric_name") or r.get("metric") or "unknown"
        v = r.get("verdict", "")
        if v == "Correct":
            by_metric[m]["correct"] += 1
        elif v == "Too Sensitive":
            by_metric[m]["too_sensitive"] += 1
        elif v == "Missed Severity":
            by_metric[m]["missed"] += 1
    noisy = [m for m, c in by_metric.items() if (c["too_sensitive"] + c["missed"]) >= 2]
    report = {
        "total_labeled": total,
        "correct": correct,
        "too_sensitive": too_sensitive,
        "missed_severity": missed,
        "accuracy_pct": round(accuracy_pct, 1),
        "false_positive_estimate": too_sensitive,
        "false_negative_estimate": missed,
        "top_noisy_metrics": noisy[:20],
        "by_metric": dict(by_metric),
    }
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
    else:
        print(json.dumps(report, indent=2))
    print(f"\nAccuracy this period: {accuracy_pct:.1f}% ({correct}/{total})", file=sys.stderr)
    if noisy:
        print(f"Top noisy metrics: {', '.join(noisy[:10])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
