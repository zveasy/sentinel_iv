"""
File-replay ingest: read JSONL or CSV line-by-line with optional speed limit to simulate live feed.
Each line → one event: {timestamp, metric, value, unit?}.
"""
import csv
import json
import os
import time
from datetime import datetime, timezone

from hb.ingest.sources.base import BaseIngestSource


def _parse_line(line: str, path: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    # Try JSON first (expect {"metric": "...", "value": ..., "timestamp": "...", "unit": "..."})
    if line.startswith("{"):
        try:
            obj = json.loads(line)
            ts = obj.get("timestamp") or obj.get("ts")
            if not ts:
                ts = datetime.now(timezone.utc).isoformat()
            return {
                "timestamp": ts,
                "metric": str(obj.get("metric", obj.get("name", ""))).strip(),
                "value": obj.get("value"),
                "unit": obj.get("unit"),
            }
        except json.JSONDecodeError:
            return None
    # CSV: metric,value,unit or timestamp,metric,value,unit
    parts = next(csv.reader([line]), [])
    if len(parts) >= 2:
        if len(parts) >= 4:
            return {"timestamp": parts[0], "metric": parts[1], "value": parts[2], "unit": parts[3] if len(parts) > 3 else None}
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metric": parts[0],
            "value": parts[1],
            "unit": parts[2] if len(parts) > 2 else None,
        }
    return None


class FileReplaySource(BaseIngestSource):
    """Read from a file (JSONL or CSV) line-by-line; optional delay_sec between lines."""

    def __init__(self, path: str, delay_sec: float = 0.0):
        self.path = path
        self.delay_sec = delay_sec
        self._fh = None
        self._header_skipped = False

    def connect(self, **kwargs) -> None:
        if not os.path.isfile(self.path):
            raise FileNotFoundError(self.path)
        self._fh = open(self.path, "r", errors="replace")
        self._header_skipped = False

    def read(self, limit: int | None = None, timeout_sec: float | None = None) -> list[dict]:
        if self._fh is None:
            self.connect()
        events = []
        count = 0
        for line in self._fh:
            if self.delay_sec > 0:
                time.sleep(self.delay_sec)
            # Skip CSV header if present
            if not self._header_skipped and "metric" in line.lower() and "value" in line.lower():
                self._header_skipped = True
                continue
            ev = _parse_line(line, self.path)
            if ev and ev.get("metric"):
                events.append(ev)
                count += 1
                if limit is not None and count >= limit:
                    break
        return events

    def close(self) -> None:
        if self._fh:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
