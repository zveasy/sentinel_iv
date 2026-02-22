"""
Resilience: circuit breaker, idempotency for ingest, checkpoint history.
"""
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional


class CircuitBreaker:
    """
    Open circuit after failure_threshold failures within window_sec; stay open for open_sec.
    """
    def __init__(self, failure_threshold: int = 5, window_sec: float = 60.0, open_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.window_sec = window_sec
        self.open_sec = open_sec
        self._failures: list[float] = []
        self._opened_at: Optional[float] = None

    def record_success(self) -> None:
        self._failures = [t for t in self._failures if time.monotonic() - t < self.window_sec]

    def record_failure(self) -> None:
        now = time.monotonic()
        self._failures.append(now)
        self._failures = [t for t in self._failures if now - t < self.window_sec]
        if len(self._failures) >= self.failure_threshold:
            self._opened_at = now

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.open_sec:
            self._opened_at = None
            self._failures = []
            return False
        return True

    def call(self, fn: Callable[[], Any]) -> Any:
        if self.is_open():
            raise RuntimeError("circuit breaker is open")
        try:
            out = fn()
            self.record_success()
            return out
        except Exception:
            self.record_failure()
            raise


def idempotency_store_path(base_dir: str = "artifacts") -> str:
    return os.path.join(base_dir, "ingest_idempotency.jsonl")


def idempotency_seen(key: str, base_dir: str = "artifacts") -> Optional[str]:
    """If key was already used, return existing out_dir (or run_id); else None."""
    path = idempotency_store_path(base_dir)
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("idempotency_key") == key:
                    return rec.get("out_dir") or rec.get("run_id")
            except json.JSONDecodeError:
                continue
    return None


def idempotency_record(key: str, run_id: str, out_dir: str, base_dir: str = "artifacts") -> None:
    path = idempotency_store_path(base_dir)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({
            "idempotency_key": key,
            "run_id": run_id,
            "out_dir": out_dir,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
        }) + "\n")


def checkpoint_history_dir(output_dir: str) -> str:
    return os.path.join(output_dir, "checkpoint_history")


def save_checkpoint_to_history(output_dir: str, checkpoint: dict, max_entries: int = 50) -> None:
    """Append checkpoint to history (rotate by max_entries)."""
    hist_dir = checkpoint_history_dir(output_dir)
    os.makedirs(hist_dir, exist_ok=True)
    path = os.path.join(hist_dir, "checkpoints.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(checkpoint) + "\n")
    # Rotate: keep last max_entries
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        if len(lines) > max_entries:
            with open(path, "w") as f:
                f.writelines(lines[-max_entries:])
    except OSError:
        pass


def load_checkpoint_history(output_dir: str, limit: int = 10) -> list[dict]:
    path = os.path.join(checkpoint_history_dir(output_dir), "checkpoints.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        lines = f.readlines()
    out = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
