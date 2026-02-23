"""
Time synchronization and clock drift handling.
Timestamp normalization, tolerance windows, resync policy.
"""
import time
from typing import Literal

ResyncPolicy = Literal["warn", "adjust", "fail"]


def load_time_config(config_path: str | None = None) -> dict:
    """Load time config from YAML. Returns dict with max_clock_skew_ms, resync_policy, tolerance_window_sec."""
    if not config_path:
        return {}
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("time", data) or {}
    except Exception:
        return {}


def normalize_timestamp(
    event_ts: float | None,
    processing_time: float | None = None,
    max_clock_skew_ms: float = 50,
    resync_policy: ResyncPolicy = "warn",
    tolerance_window_sec: float = 5.0,
) -> tuple[float | None, str | None]:
    """
    Normalize event timestamp with clock skew handling.
    event_ts: event timestamp (seconds since epoch).
    processing_time: current processing time (default: time.time()).
    Returns (normalized_ts, error_or_warning). normalized_ts is None if policy is fail and skew exceeded.
    """
    if event_ts is None:
        return None, None
    processing_time = processing_time or time.time()
    skew_sec = max_clock_skew_ms / 1000.0
    delta = abs(event_ts - processing_time)
    if delta <= skew_sec:
        return event_ts, None
    if resync_policy == "fail":
        return None, f"clock_skew_exceeded: delta={delta:.3f}s max={skew_sec}s"
    if resync_policy == "adjust":
        return float(processing_time), f"clock_adjusted: event_ts={event_ts:.3f} -> processing_time (skew={delta:.3f}s)"
    # warn
    return event_ts, f"clock_skew_warn: delta={delta:.3f}s max={skew_sec}s"


def in_tolerance_window(event_ts: float, now: float, tolerance_sec: float = 5.0) -> bool:
    """True if event_ts is within tolerance_sec of now (in-order)."""
    return abs(event_ts - now) <= tolerance_sec


def detect_clock_drift(samples: list[float], max_skew_ms: float = 50) -> dict:
    """
    samples: list of (event_ts - processing_ts) in seconds.
    Returns { "drift_detected": bool, "max_delta": float, "sample_count": int }.
    """
    if not samples:
        return {"drift_detected": False, "max_delta": 0.0, "sample_count": 0}
    max_delta = max(abs(s) for s in samples)
    skew_sec = max_skew_ms / 1000.0
    return {
        "drift_detected": max_delta > skew_sec,
        "max_delta": max_delta,
        "sample_count": len(samples),
    }
