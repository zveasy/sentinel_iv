import json
import os
import time
from datetime import datetime, timezone


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def write_heartbeat(path, status="ok", details=None):
    payload = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "details": details or {},
    }
    _ensure_dir(path)
    with open(path, "a") as f:
        f.write(json.dumps(payload) + "\n")
    return path


def tail_heartbeats(path, limit=20):
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return lines[-limit:]
