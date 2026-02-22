"""Alert sinks: emit structured events on drift/FAIL (stdout, file, webhook)."""
from hb.alerting.sinks.base import AlertSink
from hb.alerting.sinks.stdout_sink import StdoutSink
from hb.alerting.sinks.file_sink import FileSink
from hb.alerting.sinks.webhook_sink import WebhookSink
from hb.alerting.severity import severity_for_status

__all__ = ["AlertSink", "StdoutSink", "FileSink", "WebhookSink", "severity_for_status"]


def get_sinks(names: list[str], **kwargs) -> list[AlertSink]:
    """Resolve sink names to instances. names: ['stdout', 'file', 'webhook']."""
    registry = {"stdout": StdoutSink, "file": FileSink, "webhook": WebhookSink}
    out = []
    for name in names:
        name = (name or "").strip().lower()
        if name not in registry:
            continue
        out.append(registry[name](**kwargs))
    return out
