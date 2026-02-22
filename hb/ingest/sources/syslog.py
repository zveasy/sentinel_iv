"""
Syslog ingest: read from Unix socket /dev/log or a file path.
Parse RFC 5424 / common formats to {timestamp, host, program, msg, fields}.
Metric can be derived from program + msg or a pattern.
"""
import re
import socket
import os
from datetime import datetime, timezone
from typing import Any

from hb.ingest.sources.base import BaseIngestSource

# Common syslog pattern: <pri>timestamp host program[pid]: msg
SYSLOG_PAT = re.compile(
    r"^(?:<(\d+)>)?\s*(\S+\s+\d+\s+\S+)\s+(\S+)\s+(\S+)(?:\[(\d+)\])?:\s*(.*)$"
)
# RFC 5424: optional timestamp at start
ISO_TS_PAT = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z?)\s+(.*)$")


def _parse_syslog_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    ts = datetime.now(timezone.utc).isoformat()
    # Try ISO timestamp prefix
    m = ISO_TS_PAT.match(line)
    if m:
        ts, rest = m.group(1), m.group(2)
        line = rest
    m = SYSLOG_PAT.match(line)
    if m:
        pri, ts_part, host, program, pid, msg = m.groups()
        return {
            "timestamp": ts,
            "host": host or "",
            "program": program or "",
            "pid": pid,
            "msg": (msg or "").strip(),
            "metric": f"syslog_{program}" if program else "syslog",
            "value": 1,
            "unit": None,
        }
    # Fallback: whole line as message, metric = "syslog"
    return {"timestamp": ts, "host": "", "program": "", "msg": line, "metric": "syslog", "value": 1, "unit": None}


class SyslogSource(BaseIngestSource):
    """Read from /dev/log (Unix socket) or a file path."""

    def __init__(self, path: str = "/dev/log"):
        self.path = path
        self._socket: socket.socket | None = None
        self._file = None
        self._buffer = ""

    def connect(self, **kwargs) -> None:
        if self.path == "/dev/log" or self.path.startswith("/dev/"):
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            try:
                self._socket.connect(self.path)
            except (OSError, socket.error):
                self._socket.close()
                self._socket = None
                raise ConnectionError(f"Cannot connect to {self.path} (try run as root or use a file path)")
        else:
            if not os.path.isfile(self.path):
                raise FileNotFoundError(self.path)
            self._file = open(self.path, "r", errors="replace")

    def read(self, limit: int | None = None, timeout_sec: float | None = None) -> list[dict]:
        if self._socket is None and self._file is None:
            self.connect()
        events = []
        count = 0
        if self._socket:
            self._socket.settimeout(timeout_sec or 1.0)
            try:
                while limit is None or count < limit:
                    data = self._socket.recv(4096)
                    if not data:
                        break
                    line = data.decode("utf-8", errors="replace")
                    ev = _parse_syslog_line(line)
                    if ev:
                        events.append(ev)
                        count += 1
            except socket.timeout:
                pass
        elif self._file:
            for line in self._file:
                ev = _parse_syslog_line(line)
                if ev:
                    events.append(ev)
                    count += 1
                    if limit is not None and count >= limit:
                        break
        return events

    def close(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._file:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
