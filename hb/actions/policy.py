"""
Load action policy from YAML: which status/conditions map to which actions, safety gates.
"""
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ActionRule:
    """One rule: when status/conditions match, emit these actions."""
    status: list[str]  # e.g. ["FAIL", "PASS_WITH_DRIFT"]
    conditions: list[dict]  # optional: e.g. [{"min_drift_count": 1}]
    actions: list[dict]  # e.g. [{"type": "notify", "params": {"sink": "webhook"}}]
    safety_required: bool = False  # if True, require safety gate for critical actions


@dataclass
class ActionPolicy:
    """Policy: rules + safety gate config."""
    version: str = "1.0"
    rules: list[ActionRule] = field(default_factory=list)
    # Safety: e.g. require two independent conditions for shutdown
    safety_gate: dict = field(default_factory=lambda: {"require_two_conditions": True, "critical_actions": ["shutdown", "abort"]})


def _parse_rule(r: dict) -> ActionRule:
    return ActionRule(
        status=r.get("status") or [],
        conditions=r.get("conditions") or [],
        actions=r.get("actions") or [],
        safety_required=bool(r.get("safety_required")),
    )


def load_action_policy(path: str | None = None) -> ActionPolicy:
    if not path or not os.path.isfile(path):
        return ActionPolicy()
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    rules = [_parse_rule(r) for r in data.get("rules") or []]
    return ActionPolicy(
        version=str(data.get("version", "1.0")),
        rules=rules,
        safety_gate=data.get("safety_gate") or {},
    )
