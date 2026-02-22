"""
State machine for operational modes: startup, nominal, degraded, fallback, maintenance, test, emergency.
Mode-aware thresholds/invariants and baseline selection; mode transition rules + evidence.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OperationalMode(str, Enum):
    STARTUP = "startup"
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    FALLBACK = "fallback"
    MAINTENANCE = "maintenance"
    TEST = "test"
    EMERGENCY = "emergency"


# Valid transitions: from_mode -> set of allowed to_modes
MODE_TRANSITIONS: dict[OperationalMode, set[OperationalMode]] = {
    OperationalMode.STARTUP: {OperationalMode.NOMINAL, OperationalMode.DEGRADED, OperationalMode.TEST},
    OperationalMode.NOMINAL: {OperationalMode.DEGRADED, OperationalMode.FALLBACK, OperationalMode.MAINTENANCE, OperationalMode.TEST},
    OperationalMode.DEGRADED: {OperationalMode.NOMINAL, OperationalMode.FALLBACK, OperationalMode.EMERGENCY},
    OperationalMode.FALLBACK: {OperationalMode.NOMINAL, OperationalMode.DEGRADED, OperationalMode.MAINTENANCE},
    OperationalMode.MAINTENANCE: {OperationalMode.NOMINAL, OperationalMode.TEST},
    OperationalMode.TEST: {OperationalMode.NOMINAL, OperationalMode.STARTUP},
    OperationalMode.EMERGENCY: {OperationalMode.MAINTENANCE, OperationalMode.NOMINAL},
}


def parse_mode(s: str | None) -> OperationalMode | None:
    if not s:
        return None
    try:
        return OperationalMode((s or "").strip().lower())
    except ValueError:
        return None


def can_transition(from_mode: OperationalMode | None, to_mode: OperationalMode) -> bool:
    if from_mode is None:
        return True
    allowed = MODE_TRANSITIONS.get(from_mode)
    return allowed is not None and to_mode in allowed


@dataclass
class ModeTransitionEvidence:
    """Evidence for who/what changed mode (audit)."""
    from_mode: str
    to_mode: str
    ts_utc: str
    reason: str
    operator_id: str | None = None
    source: str | None = None  # e.g. "api", "daemon", "cli"


def transition_evidence(from_mode: str, to_mode: str, reason: str, operator_id: str | None = None, source: str | None = None) -> dict[str, Any]:
    return {
        "from_mode": from_mode,
        "to_mode": to_mode,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "operator_id": operator_id,
        "source": source,
    }
