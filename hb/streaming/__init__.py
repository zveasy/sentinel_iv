"""
Streaming evaluator: event-time processing, watermarks, sliding windows, continuous decisions.
Runtime mode: hb runtime --config config/runtime.yaml
"""
from hb.streaming.event_time import EventTimeClock, WatermarkPolicy
from hb.streaming.windows import SlidingWindowAggregator, WindowSpec
from hb.streaming.evaluator import StreamingEvaluator
from hb.streaming.snapshot import DecisionSnapshot
from hb.streaming.latency import LatencyRecorder

__all__ = [
    "EventTimeClock",
    "WatermarkPolicy",
    "SlidingWindowAggregator",
    "WindowSpec",
    "StreamingEvaluator",
    "DecisionSnapshot",
    "LatencyRecorder",
]
