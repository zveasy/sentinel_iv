"""
Streaming evaluator: consumes a stream of events, maintains sliding windows,
emits decisions continuously with snapshots and latency metrics.
"""
import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from hb.streaming.event_time import EventTimeClock, WatermarkPolicy
from hb.streaming.windows import SlidingWindowAggregator, WindowSpec
from hb.streaming.snapshot import DecisionSnapshot
from hb.streaming.latency import LatencyRecorder


def _config_hashes(metric_registry_path: str | None, baseline_policy_path: str | None) -> dict[str, str]:
    out = {}
    for label, path in [("metric_registry", metric_registry_path), ("baseline_policy", baseline_policy_path)]:
        if path and os.path.isfile(path):
            with open(path, "rb") as f:
                out[f"{label}_sha256"] = hashlib.sha256(f.read()).hexdigest()
    return out


class StreamingEvaluator:
    """
    True streaming evaluator: event-time, watermarks, sliding windows, continuous decisions.
    """
    def __init__(
        self,
        window_spec: WindowSpec,
        watermark_policy: WatermarkPolicy | None = None,
        compare_fn: Callable[[dict, dict], tuple[str, list, list, list, list, list, list]] | None = None,
        metric_registry_path: str | None = None,
        baseline_policy_path: str | None = None,
        max_buckets: int | None = None,
        deterministic_mode: bool = False,
    ):
        self.window_spec = window_spec
        self.clock = EventTimeClock(watermark_policy or WatermarkPolicy())
        self.aggregator = SlidingWindowAggregator(window_spec, max_buckets=max_buckets)
        self.compare_fn = compare_fn
        self.metric_registry_path = metric_registry_path
        self.baseline_policy_path = baseline_policy_path
        self.latency = LatencyRecorder()
        self.deterministic_mode = deterministic_mode

    def process_event(self, event: dict[str, Any]) -> str:
        """
        Process one event. Returns "accept" | "drop" | "buffer".
        Caller should call emit_decision() when appropriate (e.g. on watermark advance).
        """
        decision = self.clock.decide_late(event)
        if decision != "accept":
            return decision
        et = self.clock.event_time_from(event)
        if et is None:
            return "accept"
        metric = event.get("metric") or event.get("name") or ""
        try:
            value = float(event.get("value", 0))
        except (TypeError, ValueError):
            return "accept"
        self.aggregator.add(et, metric, value)
        self.aggregator.set_watermark(self.clock.watermark)
        return "accept"

    def emit_decision(
        self,
        baseline_metrics: dict,
        run_id: str | None = None,
    ) -> DecisionSnapshot | None:
        """
        Emit one decision from current window aggregates vs baseline.
        Returns DecisionSnapshot or None if no data.
        """
        t0 = time.perf_counter()
        w = self.clock.watermark
        self.aggregator.set_watermark(w)
        current = self.aggregator.get_current_aggregates(w)
        if not current:
            return None
        # current is metric -> value; compare_fn expects metric -> {value, unit, tags}
        # In deterministic_mode use sorted keys so output order is reproducible
        items = sorted(current.items()) if self.deterministic_mode else current.items()
        current_struct = {m: {"value": v, "unit": "", "tags": ""} for m, v in items if v is not None}
        if not current_struct:
            return None

        status = "PASS"
        drift_metrics: list = []
        fail_metrics: list = []
        invariant_violations: list = []
        distribution_drifts: list = []
        attribution: list = []
        warnings: list = []

        if self.compare_fn:
            status, drift_metrics, warnings, fail_metrics, invariant_violations, distribution_drifts, attribution = self.compare_fn(
                current_struct, baseline_metrics
            )

        latency_sec = time.perf_counter() - t0
        self.latency.record(latency_sec)

        decision_id = run_id or f"stream_{uuid.uuid4().hex[:12]}"
        window_start = None
        for start in sorted(self.aggregator._buckets.keys(), reverse=True):
            if w is not None and start + self.window_spec.window_size_sec <= w:
                window_start = start
                break
        if window_start is None and self.aggregator._buckets:
            window_start = max(self.aggregator._buckets.keys())

        # Deterministic mode: fixed ordering for reproducible outputs
        if self.deterministic_mode:
            drift_metrics = sorted(drift_metrics) if drift_metrics and isinstance(drift_metrics[0], str) else drift_metrics
            fail_metrics = sorted(fail_metrics) if fail_metrics else []
            invariant_violations = sorted(invariant_violations) if invariant_violations and isinstance(invariant_violations[0], str) else invariant_violations
        snapshot = DecisionSnapshot(
            decision_id=decision_id,
            ts_utc=datetime.now(timezone.utc).isoformat(),
            input_slice_ref={
                "window_start_sec": window_start,
                "window_end_sec": window_start + self.window_spec.window_size_sec if window_start is not None else None,
                "watermark_sec": w,
                "metric_count": len(current_struct),
            },
            config_ref=_config_hashes(self.metric_registry_path, self.baseline_policy_path),
            code_ref={"hb_version": os.environ.get("HB_VERSION", "dev")},
            decision_payload={
                "status": status,
                "drift_metrics": drift_metrics[:20],
                "fail_metrics": fail_metrics,
                "invariant_violations": invariant_violations[:20],
                "warnings": warnings[:10],
            },
            decision_latency_sec=latency_sec,
        )
        return snapshot

    def prune(self) -> None:
        """Prune old window state to bound memory."""
        if self.clock.watermark is not None:
            self.aggregator.prune_before(self.clock.watermark)
