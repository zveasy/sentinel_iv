"""
Prometheus-style metrics: ingest lag, decision latency, baseline match, action success.
Expose via /metrics (file or HTTP) and use in daemon/analyze.
"""
import os
import time
from typing import Any

# In-memory store; optional file sink for scrape
_gauges: dict[str, float] = {}
_counters: dict[str, float] = {}
_labels: dict[str, dict[str, str]] = {}  # metric -> {label -> value}


def gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    key = _key(name, labels)
    _gauges[key] = value
    if labels:
        _labels[key] = labels


def counter_inc(name: str, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
    key = _key(name, labels)
    _counters[key] = _counters.get(key, 0) + amount
    if labels:
        _labels[key] = labels


def _key(name: str, labels: dict[str, str] | None) -> str:
    if not labels:
        return name
    parts = sorted(f'{k}="{v}"' for k, v in labels.items())
    return name + "{" + ",".join(parts) + "}"


def ingest_lag_seconds(value: float) -> None:
    gauge("hb_ingest_lag_seconds", value)


def decision_latency_seconds(value: float) -> None:
    gauge("hb_decision_latency_seconds", value)


def baseline_match_score(value: float, program: str | None = None) -> None:
    labels = {} if not program else {"program": program}
    gauge("hb_baseline_match_score", value, labels if labels else None)


def action_success_total(success: bool, action: str | None = None) -> None:
    labels = {"result": "success" if success else "failure"}
    if action:
        labels["action"] = action
    counter_inc("hb_action_success_total", 1.0, labels)


def _metric_name(key: str) -> str:
    return key.split("{")[0] if "{" in key else key


def render_prometheus() -> str:
    """Render metrics in Prometheus text exposition format."""
    out = []
    seen = set()
    for key in sorted(_gauges.keys()):
        name = _metric_name(key)
        if name not in seen:
            out.append(f"# TYPE {name} gauge\n")
            seen.add(name)
    for key, value in sorted(_gauges.items()):
        out.append(f"{key} {value}\n")
    for key in sorted(_counters.keys()):
        name = _metric_name(key)
        if name not in seen:
            out.append(f"# TYPE {name} counter\n")
            seen.add(name)
    for key, value in sorted(_counters.items()):
        out.append(f"{key} {value}\n")
    return "".join(out)


def write_metrics_file(path: str) -> None:
    try:
        with open(path, "w") as f:
            f.write(render_prometheus())
    except OSError:
        pass


def reset() -> None:
    """Reset all metrics (e.g. for tests)."""
    _gauges.clear()
    _counters.clear()
    _labels.clear()
