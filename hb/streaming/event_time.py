"""
Event-time processing: handle late and out-of-order events via watermarks.
Event has event_time (when it happened) and processing_time (when we saw it).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class WatermarkPolicy:
    """When to advance watermark and how to handle late events."""
    # Advance watermark to max_event_time - allowed_lateness_sec
    allowed_lateness_sec: float = 60.0
    # Emit watermark every watermark_interval_sec if new max event seen
    watermark_interval_sec: float = 1.0
    # Late events: "drop" | "buffer" (buffer until next window close) | "side_output"
    late_event_policy: str = "drop"


def _parse_ts(ts: str | float | None) -> float | None:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (TypeError, ValueError):
        return None


class EventTimeClock:
    """
    Tracks event-time watermark and classifies events as on-time vs late.
    """
    def __init__(self, policy: WatermarkPolicy | None = None):
        self.policy = policy or WatermarkPolicy()
        self._max_event_time: float | None = None
        self._watermark: float | None = None
        self._last_watermark_emit: float | None = None

    def event_time_from(self, event: dict[str, Any]) -> float | None:
        """Extract event time (seconds since epoch) from event."""
        ts = event.get("event_time") or event.get("timestamp") or event.get("ts")
        return _parse_ts(ts)

    def update(self, event_time: float, processing_time: float | None = None) -> None:
        """Observe an event time; advance max and possibly watermark."""
        if event_time is None:
            return
        if self._max_event_time is None or event_time > self._max_event_time:
            self._max_event_time = event_time
        # Watermark = max_event_time - allowed_lateness
        w = self._max_event_time - self.policy.allowed_lateness_sec
        if self._watermark is None or w > self._watermark:
            self._watermark = w

    def is_late(self, event_time: float) -> bool:
        """True if event is after current watermark (late)."""
        if self._watermark is None:
            return False
        return event_time < self._watermark

    @property
    def watermark(self) -> float | None:
        return self._watermark

    @property
    def max_event_time(self) -> float | None:
        return self._max_event_time

    def decide_late(self, event: dict[str, Any]) -> str:
        """
        Given event, return "accept" | "drop" | "buffer" per policy.
        Caller should call update() for accepted events.
        """
        et = self.event_time_from(event)
        if et is None:
            return "accept"
        if not self.is_late(et):
            self.update(et)
            return "accept"
        return self.policy.late_event_policy
