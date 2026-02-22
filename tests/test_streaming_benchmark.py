"""
Streaming evaluator benchmark and regression tests (roadmap 5.3.2).
Run as regression: pytest tests/test_streaming_benchmark.py -v
Optional: HB_STREAMING_BENCH_EVENTS=5000 HB_STREAMING_BENCH_MAX_S=2.0 to assert throughput.
"""
import os
import time

import pytest

from hb.streaming.evaluator import StreamingEvaluator
from hb.streaming.windows import WindowSpec
from hb.streaming.event_time import WatermarkPolicy


def _make_compare_fn():
    def compare_fn(current: dict, baseline: dict):
        status = "PASS"
        drift_metrics = []
        fail_metrics = []
        invariant_violations = []
        distribution_drifts = []
        warnings = []
        attribution = []
        return status, drift_metrics, warnings, fail_metrics, invariant_violations, distribution_drifts, attribution
    return compare_fn


def _synthetic_events(n: int, base_ts: float | None = None):
    """Yield n events with event_time, metric, value for streaming ingest."""
    base_ts = base_ts or time.time() - 300
    metrics = ["latency_ms", "throughput", "error_rate", "cpu_pct", "mem_pct"]
    for i in range(n):
        t = base_ts + i * 0.1
        yield {
            "event_time": t,
            "metric": metrics[i % len(metrics)],
            "value": 10.0 + (i % 100) * 0.5,
        }


def test_streaming_evaluator_smoke():
    """Smoke test: build evaluator, push events, emit decision."""
    spec = WindowSpec(window_size_sec=10.0, slide_sec=1.0)
    policy = WatermarkPolicy(allowed_lateness_sec=5.0, late_event_policy="drop")
    evaluator = StreamingEvaluator(
        window_spec=spec,
        watermark_policy=policy,
        compare_fn=_make_compare_fn(),
        max_buckets=100,
    )
    events = list(_synthetic_events(200))
    for ev in events:
        evaluator.process_event(ev)
    snapshot = evaluator.emit_decision(baseline_metrics={})
    assert snapshot is not None
    assert "status" in snapshot.decision_payload
    assert snapshot.decision_payload["status"] == "PASS"


def test_streaming_evaluator_benchmark_throughput():
    """Regression: process N events and optionally assert max time (CI regression)."""
    n_events = int(os.environ.get("HB_STREAMING_BENCH_EVENTS", "2000"))
    max_sec = os.environ.get("HB_STREAMING_BENCH_MAX_S")
    if max_sec is not None:
        max_sec = float(max_sec)
    spec = WindowSpec(window_size_sec=10.0, slide_sec=1.0)
    policy = WatermarkPolicy(allowed_lateness_sec=5.0, late_event_policy="drop")
    evaluator = StreamingEvaluator(
        window_spec=spec,
        watermark_policy=policy,
        compare_fn=_make_compare_fn(),
        max_buckets=500,
    )
    events = list(_synthetic_events(n_events))
    t0 = time.perf_counter()
    for ev in events:
        evaluator.process_event(ev)
    snapshot = evaluator.emit_decision(baseline_metrics={})
    elapsed = time.perf_counter() - t0
    assert snapshot is not None
    if max_sec is not None:
        assert elapsed <= max_sec, f"streaming benchmark: {n_events} events in {elapsed:.3f}s (max {max_sec}s)"


def test_streaming_max_buckets_eviction():
    """With max_buckets set, oldest windows are evicted; evaluator still produces a decision."""
    spec = WindowSpec(window_size_sec=2.0, slide_sec=0.5)
    policy = WatermarkPolicy(allowed_lateness_sec=1.0, late_event_policy="drop")
    evaluator = StreamingEvaluator(
        window_spec=spec,
        watermark_policy=policy,
        compare_fn=_make_compare_fn(),
        max_buckets=10,
    )
    # Enough events to create many windows so eviction kicks in
    events = list(_synthetic_events(500, base_ts=1000.0))
    for ev in events:
        evaluator.process_event(ev)
    assert len(evaluator.aggregator._buckets) <= 10
    snapshot = evaluator.emit_decision(baseline_metrics={})
    assert snapshot is not None
