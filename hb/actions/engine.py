"""
Action engine: evaluate policy against decision status, run safety gates, execute or dry-run.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from hb.actions.policy import ActionPolicy, load_action_policy
from hb.actions.types import ACTION_TYPES, SAFETY_CRITICAL_ACTIONS


def _matches_conditions(conditions: list[dict], context: dict) -> bool:
    for c in conditions:
        key = c.get("key") or c.get("metric")
        op = c.get("op", ">=")
        val = c.get("value")
        ctx_val = context.get(key)
        if op == ">=" and (ctx_val is None or ctx_val < val):
            return False
        if op == ">" and (ctx_val is None or ctx_val <= val):
            return False
        if op == "==" and ctx_val != val:
            return False
    return True


def _safety_gate_passed(
    policy: ActionPolicy,
    action_type: str,
    context: dict,
    independent_conditions: list[dict],
) -> bool:
    """Require two independent conditions for critical actions if configured."""
    if action_type not in SAFETY_CRITICAL_ACTIONS:
        return True
    gate = policy.safety_gate or {}
    if not gate.get("require_two_conditions"):
        return True
    # Caller must pass at least two independent condition checks (e.g. status FAIL + baseline_confidence < 0.5)
    if len(independent_conditions) >= 2:
        return True
    return False


class ActionEngine:
    """
    Execute actions from policy given decision status and context.
    Supports dry_run (would-have-done), idempotency, retries, and safety gates.
    """
    def __init__(self, policy: ActionPolicy | None = None, policy_path: str | None = None):
        self.policy = policy or load_action_policy(policy_path)

    def propose_actions(
        self,
        status: str,
        context: dict | None = None,
        independent_conditions: list[dict] | None = None,
    ) -> list[dict]:
        """
        Return list of actions that would be executed (type, params, safety_gate_passed).
        Does not execute; use for dry-run.
        """
        context = context or {}
        independent_conditions = independent_conditions or []
        out = []
        for rule in self.policy.rules:
            if status not in rule.status:
                continue
            if not _matches_conditions(rule.conditions, context):
                continue
            for action_spec in rule.actions:
                action_type = action_spec.get("type") or action_spec.get("action")
                if action_type not in ACTION_TYPES:
                    continue
                safety_ok = _safety_gate_passed(
                    self.policy, action_type, context, independent_conditions
                )
                out.append({
                    "type": action_type,
                    "params": action_spec.get("params") or {},
                    "safety_gate_passed": safety_ok,
                    "would_execute": safety_ok,
                })
        return out

    def execute(
        self,
        status: str,
        context: dict | None = None,
        independent_conditions: list[dict] | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        run_id: str | None = None,
        decision_id: str | None = None,
        conn=None,
    ) -> list[dict]:
        """
        Propose and, if not dry_run, record in action ledger. Actual side effects
        (webhook, etc.) are done by callers or by a separate executor that reads the ledger.
        Returns list of {action_id, type, status, dry_run, safety_gate_passed}.
        """
        proposed = self.propose_actions(status, context, independent_conditions)
        results = []
        for item in proposed:
            action_id = str(uuid.uuid4())
            if dry_run:
                results.append({
                    "action_id": action_id,
                    "type": item["type"],
                    "status": "dry_run",
                    "would_have_done": item,
                    "dry_run": True,
                    "safety_gate_passed": item["safety_gate_passed"],
                })
                continue
            if not item["safety_gate_passed"]:
                results.append({
                    "action_id": action_id,
                    "type": item["type"],
                    "status": "blocked",
                    "reason": "safety_gate_not_passed",
                    "dry_run": False,
                    "safety_gate_passed": False,
                })
                continue
            if conn is not None:
                from hb.registry import action_ledger_insert, action_ledger_by_idempotency
                existing = action_ledger_by_idempotency(conn, idempotency_key) if idempotency_key else None
                if existing:
                    results.append({
                        "action_id": existing[0],
                        "type": item["type"],
                        "status": "idempotent_skip",
                        "existing_status": existing[1],
                        "dry_run": False,
                        "safety_gate_passed": True,
                    })
                    continue
                action_ledger_insert(
                    conn,
                    action_id=action_id,
                    action_type=item["type"],
                    status="pending",
                    payload={"params": item["params"], **context},
                    run_id=run_id,
                    decision_id=decision_id,
                    idempotency_key=idempotency_key,
                    safety_gate_passed=True,
                    dry_run=0,
                )
            results.append({
                "action_id": action_id,
                "type": item["type"],
                "status": "pending",
                "dry_run": False,
                "safety_gate_passed": True,
            })
        return results


def execute_actions(
    status: str,
    context: dict | None = None,
    policy_path: str | None = None,
    dry_run: bool = False,
    idempotency_key: str | None = None,
    conn=None,
    run_id: str | None = None,
    decision_id: str | None = None,
) -> list[dict]:
    """
    Convenience: create engine, execute, return results.
    """
    engine = ActionEngine(policy_path=policy_path)
    return engine.execute(
        status=status,
        context=context,
        dry_run=dry_run,
        idempotency_key=idempotency_key,
        conn=conn,
        run_id=run_id,
        decision_id=decision_id,
    )
