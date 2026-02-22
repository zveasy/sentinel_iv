"""
Live telemetry ingest: source registry and adapters.
Use get_source(name) for mqtt, syslog, file_replay, kafka. File-based ingest (pba_excel, etc.) remains in hb.adapters.
"""
from hb.ingest.sources.base import BaseIngestSource
from hb.ingest.sources.file_replay import FileReplaySource
from hb.ingest.sources.mqtt import MQTTSource
from hb.ingest.sources.syslog import SyslogSource

_SOURCES = {
    "file_replay": FileReplaySource,
    "mqtt": MQTTSource,
    "syslog": SyslogSource,
}
try:
    from hb.ingest.sources.kafka import KafkaSource
    _SOURCES["kafka"] = KafkaSource
except Exception:
    pass


def get_source(name: str, **kwargs) -> BaseIngestSource:
    """Return an ingest source instance. name: file_replay, mqtt, syslog, kafka."""
    if name not in _SOURCES:
        raise ValueError(f"unknown ingest source: {name}. Available: {list(_SOURCES)}")
    return _SOURCES[name](**kwargs)
