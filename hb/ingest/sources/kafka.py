"""
Kafka ingest source: consume telemetry from a Kafka topic (same event shape as MQTT/syslog).
Requires: pip install confluent-kafka or kafka-python.
"""
from typing import Any

from hb.ingest.sources.base import BaseIngestSource


class KafkaSource(BaseIngestSource):
    """Consume events from Kafka; emit same shape as other sources: {timestamp, metric, value, unit?, ...}."""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "hb.telemetry", group_id: str = "hb-ingest"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self._consumer = None

    def connect(self, **kwargs) -> None:
        try:
            from confluent_kafka import Consumer
        except ImportError:
            raise RuntimeError("confluent-kafka not installed; pip install confluent-kafka")
        self._consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
        })
        self._consumer.subscribe([self.topic])

    def read(self, limit: int | None = None, timeout_sec: float | None = None) -> list[dict[str, Any]]:
        if not self._consumer:
            return []
        import json
        out = []
        limit = limit or 100
        timeout_ms = int((timeout_sec or 5.0) * 1000)
        while len(out) < limit:
            msg = self._consumer.poll(timeout=min(1.0, timeout_sec or 1.0) if timeout_sec else 1.0)
            if msg is None:
                break
            if msg.error():
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, AttributeError):
                continue
            if isinstance(payload, dict) and "timestamp" not in payload:
                ts = getattr(msg, "timestamp", lambda: (0, None))()
                payload["timestamp"] = ts[1] if isinstance(ts, (list, tuple)) and len(ts) > 1 else None
            out.append(payload)
        return out

    def close(self) -> None:
        if self._consumer:
            self._consumer.close()
            self._consumer = None
