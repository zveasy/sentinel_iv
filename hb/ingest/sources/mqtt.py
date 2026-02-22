"""
MQTT ingest: subscribe to topics, parse JSON or key=value payloads to {timestamp, metric, value, unit}.
Requires paho-mqtt. Optional: --broker, --topic, --qos.
"""
import json
import time
from datetime import datetime, timezone
from typing import Any

from hb.ingest.sources.base import BaseIngestSource

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None  # type: ignore


def _parse_payload(payload: bytes, topic: str) -> dict[str, Any] | None:
    try:
        text = payload.decode("utf-8", errors="replace").strip()
    except Exception:
        return None
    ts = datetime.now(timezone.utc).isoformat()
    # JSON: {"metric": "x", "value": 1.0, "unit": "ms"}
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            return {
                "timestamp": obj.get("timestamp", ts),
                "metric": str(obj.get("metric", obj.get("name", topic.split("/")[-1] or "unknown"))),
                "value": obj.get("value"),
                "unit": obj.get("unit"),
            }
        except json.JSONDecodeError:
            pass
    # key=value or metric=value
    parts = text.split("=", 1)
    if len(parts) == 2:
        return {"timestamp": ts, "metric": parts[0].strip(), "value": parts[1].strip(), "unit": None}
    return {"timestamp": ts, "metric": topic.replace("/", "_"), "value": text, "unit": None}


class MQTTSource(BaseIngestSource):
    """Subscribe to MQTT topic(s), collect messages into events."""

    def __init__(self, broker: str = "tcp://localhost:1883", topic: str = "hb/metrics/#", qos: int = 0):
        if mqtt is None:
            raise ImportError("paho-mqtt is required for MQTT ingest. Install with: pip install paho-mqtt")
        self.broker = broker
        self.topic = topic
        self.qos = qos
        self._client: Any = None
        self._events: list[dict] = []
        self._connected = False

    def connect(self, **kwargs) -> None:
        self._client = mqtt.Client()
        self._events = []

        def on_connect(client, userdata, flags, reason_code, properties=None):
            self._connected = True
            client.subscribe(self.topic, qos=self.qos)

        def on_message(client, userdata, msg):
            ev = _parse_payload(msg.payload, msg.topic)
            if ev:
                self._events.append(ev)

        self._client.on_connect = on_connect
        self._client.on_message = on_message
        # broker can be tcp://host:port or host
        host = self.broker.replace("tcp://", "").split("/")[0]
        if ":" in host:
            host, port_s = host.rsplit(":", 1)
            port = int(port_s)
        else:
            port = 1883
        self._client.connect(host, port, 60)
        self._client.loop_start()
        # Wait for connect
        for _ in range(50):
            if self._connected:
                break
            time.sleep(0.1)
        if not self._connected:
            raise ConnectionError(f"MQTT connect timeout to {host}:{port}")

    def read(self, limit: int | None = None, timeout_sec: float | None = None) -> list[dict]:
        if self._client is None:
            self.connect()
        self._events = []
        deadline = time.time() + (timeout_sec or 5.0)
        while time.time() < deadline:
            self._client.loop(timeout=0.2)
            if limit is not None and len(self._events) >= limit:
                break
            time.sleep(0.1)
        out = self._events[:limit] if limit else self._events
        self._events = self._events[len(out):]
        return out

    def close(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._connected = False
