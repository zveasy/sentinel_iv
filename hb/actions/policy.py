"""
Load action policy from YAML: which status/conditions map to which actions, safety gates.
"""
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


# Action tiers: 0=observe only, 1=notify+evidence, 2=degrade/failover, 3=abort/shutdown (2-man + persistence)
ACTION_TIER_BY_TYPE = {
    "notify": 1,
    "degrade": 2,
    "failover": 2,
    "rate_limit": 2,
    "isolate": 2,
    "abort": 3,
    "shutdown": 3,
}


@dataclass
class ActionRule:
    """One rule: when status/conditions match, emit these actions."""
    status: list[str]  # e.g. ["FAIL", "PASS_WITH_DRIFT"]
    conditions: list[dict]  # optional: e.g. [{"min_drift_count": 1}]
    actions: list[dict]  # e.g. [{"type": "notify", "params": {...}, "tier": 1}]
    safety_required: bool = False
    tier: int | None = None  # override tier for this rule (else from action type)


@dataclass
class ActionPolicy:
    """Policy: rules + safety gate config + decision authority (confidence and multi-signal gating)."""
    version: str = "1.0"
    rules: list[ActionRule] = field(default_factory=list)
    hb_mode: str = "normal"  # normal | safe: safe = only notify, no Tier 3
    # Safety: e.g. require two independent conditions for shutdown
    safety_gate: dict = field(default_factory=lambda: {"require_two_conditions": True, "critical_actions": ["shutdown", "abort"]})
    # Decision authority: don't allow actions unless confidence and multi-signal bars are met
    decision_authority: dict = field(default_factory=lambda: {
        "min_confidence": 0.0,
        "min_baseline_confidence": 0.0,
        "min_metrics_for_critical": 2,
        "time_persistence_cycles": 0,
    })
    # Fail-safe: when True, no shutdown/abort (only observe/notify). Set when timing SLO missed.
    fail_safe_on_timing: bool = False
    # Max allowed tier (0-3). Actions with tier > max_allowed_tier are denied.
    max_allowed_tier: int | None = None  # None = allow all
    # Tier 3 requires 2-man rule: context must include approval_token or second_approver_id
    require_two_man_for_tier3: bool = True
    # min_baseline_confidence_for_critical: below this, downgrade or block Tier 3 actions
    min_baseline_confidence_for_critical: float = 0.0


def _parse_rule(r: dict) -> ActionRule:
    return ActionRule(
        status=r.get("status") or [],
        conditions=r.get("conditions") or [],
        actions=r.get("actions") or [],
        safety_required=bool(r.get("safety_required")),
        tier=r.get("tier"),
    )


def load_action_policy(path: str | None = None) -> ActionPolicy:
    if not path or not os.path.isfile(path):
        return ActionPolicy()
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    rules = [_parse_rule(r) for r in data.get("rules") or []]
    _da = data.get("decision_authority") or {}
    decision_authority = {
        "min_confidence": _da.get("min_confidence", 0.0),
        "min_baseline_confidence": _da.get("min_baseline_confidence", 0.0),
        "min_metrics_for_critical": _da.get("min_metrics_for_critical", 2),
        "time_persistence_cycles": _da.get("time_persistence_cycles", 0),
    }
    return ActionPolicy(
        version=str(data.get("version", "1.0")),
        rules=rules,
        safety_gate=data.get("safety_gate") or {},
        decision_authority=decision_authority,
        fail_safe_on_timing=bool(data.get("fail_safe_on_timing", False)),
        max_allowed_tier=data.get("max_allowed_tier"),
        require_two_man_for_tier3=bool(data.get("require_two_man_for_tier3", True)),
        min_baseline_confidence_for_critical=float(data.get("min_baseline_confidence_for_critical", 0) or 0),
        hb_mode=str(data.get("hb_mode", "normal") or "normal").lower(),
    )
