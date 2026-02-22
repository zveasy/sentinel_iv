"""
Optional OpenTelemetry tracing: ingest → decision → action.
No-op if opentelemetry-api is not installed. Use for 5.2.3 observability.
"""
from typing import Any, Callable, Optional

_tracer = None


def _get_tracer():
    global _tracer
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace
        _tracer = trace.get_tracer("hb", "0.3.0")
        return _tracer
    except ImportError:
        return None


def span(name: str, attributes: Optional[dict[str, Any]] = None):
    """Context manager that creates a span when OTel is available; no-op otherwise."""
    t = _get_tracer()
    if t is None:
        from contextlib import nullcontext
        return nullcontext()
    from opentelemetry import trace
    return t.start_as_current_span(name, attributes=attributes or {})


def trace_analyze(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: wrap fn in an 'hb.analyze' span when OTel is available."""
    t = _get_tracer()
    if t is None:
        return fn

    def wrapper(*args, **kwargs):
        with t.start_as_current_span("hb.analyze"):
            return fn(*args, **kwargs)
    return wrapper
