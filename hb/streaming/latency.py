"""
Decision latency tracking: p50/p95 decision time for latency budgets.
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LatencyRecorder:
    """Records decision latencies and exposes p50/p95."""
    max_samples: int = 1000
    _samples: deque = field(default_factory=deque)

    def record(self, latency_sec: float) -> None:
        self._samples.append(latency_sec)
        while len(self._samples) > self.max_samples:
            self._samples.popleft()

    def p50(self) -> Optional[float]:
        return self._percentile(0.50)

    def p95(self) -> Optional[float]:
        return self._percentile(0.95)

    def _percentile(self, p: float) -> Optional[float]:
        if not self._samples:
            return None
        sorted_s = sorted(self._samples)
        idx = max(0, int(len(sorted_s) * p) - 1)
        return sorted_s[idx]

    def snapshot(self) -> dict:
        """For metrics export (Prometheus or report)."""
        return {
            "count": len(self._samples),
            "p50_sec": self.p50(),
            "p95_sec": self.p95(),
        }
