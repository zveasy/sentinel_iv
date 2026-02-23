#!/usr/bin/env python3
"""
Load generator for HB: emit telemetry events at configurable rate (10k–100k events/sec profiles).
Use for soak tests and worst-case latency characterization (p99.9).
Output: JSONL to stdout or file (for file_replay) or optional Kafka.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Optional Kafka
try:
    from kafka import KafkaProducer
    _KAFKA = True
except ImportError:
    _KAFKA = False


def _ts():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def emit_event(metric: str, value: float, unit: str = "", tags: str = "", out=None, producer=None, topic: str = "hb/events"):
    ev = {"_ts": time.time(), "timestamp": _ts(), "metric": metric, "value": value, "unit": unit, "tags": tags}
    line = json.dumps(ev) + "\n"
    if out:
        out.write(line)
        out.flush()
    if producer:
        producer.send(topic, value=ev)
    return line


def main():
    ap = argparse.ArgumentParser(description="HB load generator: 10k–100k events/sec profiles")
    ap.add_argument("--profile", default="10k", choices=["10k", "50k", "100k"], help="Target events/sec")
    ap.add_argument("--duration-sec", type=float, default=10.0, help="Run duration")
    ap.add_argument("--metrics", type=int, default=50, help="Number of distinct metrics")
    ap.add_argument("--out", default=None, help="Output JSONL file (default: stdout)")
    ap.add_argument("--kafka", default=None, help="Kafka broker (e.g. localhost:9092) to publish")
    ap.add_argument("--topic", default="hb/events", help="Kafka topic")
    args = ap.parse_args()
    rate = {"10k": 10_000, "50k": 50_000, "100k": 100_000}[args.profile]
    out = open(args.out, "w") if args.out else sys.stdout
    producer = None
    if args.kafka:
        if not _KAFKA:
            print("kafka-python required for --kafka", file=sys.stderr)
            return 1
        producer = KafkaProducer(
            bootstrap_servers=args.kafka.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
    interval = 1.0 / rate if rate else 0
    start = time.perf_counter()
    count = 0
    deadline = start + args.duration_sec
    while time.perf_counter() < deadline:
        for i in range(args.metrics):
            emit_event(f"metric_{i}", 10.0 + (i % 100), "ms", "", out, producer, args.topic)
            count += 1
        # Throttle to approximate rate
        elapsed = time.perf_counter() - start
        target_count = int(elapsed * rate)
        if count >= target_count and interval > 0:
            time.sleep(max(0, interval * (count - target_count)))
    if producer:
        producer.flush()
        producer.close()
    if args.out:
        out.close()
    elapsed = time.perf_counter() - start
    print(f"load_gen: profile={args.profile} duration={elapsed:.1f}s count={count} rate={count/elapsed:.0f}/s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
