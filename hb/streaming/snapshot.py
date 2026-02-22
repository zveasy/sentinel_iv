"""
Deterministic decision snapshot: what inputs/config produced a decision.
Enables defensible replay and audit.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DecisionSnapshot:
    """
    Immutable record of a single streaming decision for audit and replay.
    """
    decision_id: str
    ts_utc: str
    # Input slice reference (e.g. window range, or file/offset)
    input_slice_ref: dict[str, Any]  # e.g. {"window_start": 123.0, "window_end": 124.0, "event_count": 42}
    # Config/registry version at decision time
    config_ref: dict[str, Any]     # e.g. {"metric_registry_sha256": "abc...", "baseline_policy_sha256": "def..."}
    # Code/SBOM reference (optional)
    code_ref: dict[str, Any]      # e.g. {"sbom_version": "1.0", "hb_version": "0.3.0"}
    # Decision payload (status, drift_metrics, etc.)
    decision_payload: dict[str, Any]
    # Latency of this decision (sec)
    decision_latency_sec: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "ts_utc": self.ts_utc,
            "input_slice_ref": self.input_slice_ref,
            "config_ref": self.config_ref,
            "code_ref": self.code_ref,
            "decision_payload": self.decision_payload,
            "decision_latency_sec": self.decision_latency_sec,
        }
