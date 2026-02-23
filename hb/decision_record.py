"""
First-class decision record: canonical API output for operators, auditors, and systems.
Written as decision_record.json alongside reports; consumed by evidence pack and integrations.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


def build_decision_record(
    decision_id: str,
    status: str,
    confidence: float | None = None,
    baseline_confidence: float | None = None,
    trigger_metrics: list[str] | None = None,
    action_requested: str | None = None,
    action_allowed: bool = True,
    reason: str | None = None,
    policy_version: str | None = None,
    config_hash: str | None = None,
    evidence_ref: str | None = None,
    run_id: str | None = None,
    baseline_run_id: str | None = None,
    correlation_id: str | None = None,
    extra: dict | None = None,
    decision_confidence: float | None = None,
    schema_version: str = "1.0",
) -> dict[str, Any]:
    """
    Build the canonical decision record object.
    """
    rec = {
        "schema_version": schema_version,
        "decision_id": decision_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "confidence": confidence,
        "baseline_confidence": baseline_confidence,
        "trigger_metrics": trigger_metrics or [],
        "action_requested": action_requested,
        "action_allowed": action_allowed,
        "reason": reason or "",
        "policy_version": policy_version or "",
        "config_hash": config_hash or "",
        "evidence_ref": evidence_ref or "",
        "run_id": run_id,
        "baseline_run_id": baseline_run_id,
        "correlation_id": correlation_id,
    }
    if decision_confidence is not None:
        rec["decision_confidence"] = decision_confidence
    if extra:
        rec["extra"] = extra
    return rec


def write_decision_record(
    report_dir: str,
    record: dict[str, Any],
    path: str | None = None,
) -> str:
    """Write decision_record.json to report_dir. Returns path written."""
    out_path = path or os.path.join(report_dir, "decision_record.json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(record, f, indent=2)
    return out_path


def decision_record_from_analyze(
    run_id: str,
    status: str,
    baseline_run_id: str | None = None,
    confidence: float | None = None,
    baseline_confidence: float | None = None,
    trigger_metrics: list[str] | None = None,
    action_requested: str | None = None,
    action_allowed: bool = True,
    reason: str | None = None,
    policy_version: str | None = None,
    config_hashes: dict | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build decision record from analyze output (report_dir and hashes from report)."""
    config_hash = ""
    if config_hashes:
        config_hash = hashlib.sha256(json.dumps(config_hashes, sort_keys=True).encode()).hexdigest()
    return build_decision_record(
        decision_id=run_id,
        status=status,
        confidence=confidence,
        baseline_confidence=baseline_confidence,
        trigger_metrics=trigger_metrics,
        action_requested=action_requested,
        action_allowed=action_allowed,
        reason=reason,
        policy_version=policy_version,
        config_hash=config_hash,
        evidence_ref=os.path.join(run_id, "drift_report.json") if run_id else "",
        run_id=run_id,
        baseline_run_id=baseline_run_id,
        correlation_id=correlation_id,
    )
