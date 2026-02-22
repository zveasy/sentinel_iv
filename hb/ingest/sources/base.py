"""
Base class for live telemetry ingest sources.
Sources produce a stream of raw events: {timestamp, metric, value, unit?, ...}.
"""
import abc
from typing import Any, Iterator


class BaseIngestSource(abc.ABC):
    """Adapter for live or replayed telemetry. connect() then read()/stream(); close() when done."""

    @abc.abstractmethod
    def connect(self, **kwargs) -> None:
        """Establish connection (e.g. MQTT broker, socket). No-op for file-based sources."""
        pass

    @abc.abstractmethod
    def read(self, limit: int | None = None, timeout_sec: float | None = None) -> list[dict[str, Any]]:
        """Read up to `limit` events (or until timeout). Returns list of {timestamp, metric, value, unit?, ...}."""
        pass

    def stream(self, timeout_sec: float | None = None) -> Iterator[dict[str, Any]]:
        """Yield events one by one. Default: wrap read() in a loop."""
        while True:
            batch = self.read(limit=1, timeout_sec=timeout_sec or 1.0)
            if not batch:
                break
            for event in batch:
                yield event

    @abc.abstractmethod
    def close(self) -> None:
        """Release connection/resources."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False
