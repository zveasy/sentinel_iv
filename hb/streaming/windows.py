"""
Sliding windows with incremental aggregates (no full recompute).
Supports 250ms, 1s, 10s etc. via window_size_sec and slide_sec.
"""
from dataclasses import dataclass, field
from typing import Any, Callable
import time


@dataclass
class WindowSpec:
    """Sliding window: size and slide interval in seconds."""
    window_size_sec: float   # e.g. 1.0, 10.0
    slide_sec: float         # e.g. 0.25, 1.0 (must be <= window_size_sec)
    # Optional: align to epoch for determinism
    align_epoch_sec: float | None = None


def _default_aggregate(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


class SlidingWindowAggregator:
    """
    Incremental sliding window: (event_time, metric, value) → per-window aggregates.
    Uses buckets keyed by window start; add() updates buckets; get_current() returns
    aggregates for windows that are complete up to watermark (or latest).
    Optional max_buckets: when set, evict oldest windows to keep memory bounded.
    """
    def __init__(
        self,
        spec: WindowSpec,
        aggregate: Callable[[list[float]], float | None] | None = None,
        max_buckets: int | None = None,
    ):
        self.spec = spec
        self.aggregate = aggregate or _default_aggregate
        self.max_buckets = max_buckets
        # window_start_sec -> metric -> list of (event_time, value)
        self._buckets: dict[float, dict[str, list[tuple[float, float]]]] = {}
        self._watermark: float | None = None

    def _window_start(self, event_time: float) -> float:
        if self.spec.align_epoch_sec is not None:
            offset = event_time - self.spec.align_epoch_sec
        else:
            offset = event_time
        # Which slide interval this falls into
        idx = int(offset / self.spec.slide_sec)
        start = self.spec.align_epoch_sec or 0
        start += idx * self.spec.slide_sec
        return start

    def add(self, event_time: float, metric: str, value: float) -> None:
        """Add (event_time, metric, value); update all overlapping windows."""
        # All window starts that contain this event_time
        start = self._window_start(event_time)
        window_end = start + self.spec.window_size_sec
        t = start
        while t < event_time + 1e-9:
            if event_time < t + self.spec.window_size_sec:
                if t not in self._buckets:
                    self._buckets[t] = {}
                if metric not in self._buckets[t]:
                    self._buckets[t][metric] = []
                self._buckets[t][metric].append((event_time, value))
            t += self.spec.slide_sec
            if t >= window_end + self.spec.slide_sec:
                break
        if self.max_buckets is not None and len(self._buckets) > self.max_buckets:
            for start in sorted(self._buckets.keys())[: len(self._buckets) - self.max_buckets]:
                del self._buckets[start]

    def set_watermark(self, w: float) -> None:
        self._watermark = w

    def get_aggregates_for_window(self, window_start: float) -> dict[str, float | None]:
        """Return metric -> aggregate value for the window starting at window_start."""
        bucket = self._buckets.get(window_start, {})
        out = {}
        for metric, pairs in bucket.items():
            values = [v for _, v in pairs]
            out[metric] = self.aggregate(values)
        return out

    def get_current_aggregates(self, up_to_watermark: float | None = None) -> dict[str, float | None]:
        """
        Return aggregates for the most recent complete window(s) up to watermark.
        If no watermark, use the latest window that has data.
        """
        w = up_to_watermark if up_to_watermark is not None else self._watermark
        if not self._buckets:
            return {}
        starts = sorted(self._buckets.keys(), reverse=True)
        # Pick latest window that is fully behind watermark (window_end <= w)
        for start in starts:
            window_end = start + self.spec.window_size_sec
            if w is not None and window_end > w:
                continue
            return self.get_aggregates_for_window(start)
        # No window complete yet; return latest partial if no watermark
        if w is None and starts:
            return self.get_aggregates_for_window(starts[0])
        return {}

    def prune_before(self, watermark: float) -> None:
        """Drop windows that are fully before watermark to bound memory."""
        cutoff = watermark - self.spec.window_size_sec - self.spec.slide_sec * 2
        for start in list(self._buckets.keys()):
            if start < cutoff:
                del self._buckets[start]
