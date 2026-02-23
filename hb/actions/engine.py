"""
Action engine: evaluate policy against decision status, run safety gates, execute or dry-run.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from hb.actions.policy import ActionPolicy, load_action_policy, ACTION_TIER_BY_TYPE
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
        if op == "<" and (ctx_val is None or ctx_val >= val):
            return False
        if op == "<=" and (ctx_val is None or ctx_val > val):
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


def _action_allowed(policy: ActionPolicy, action_type: str, context: dict) -> tuple[bool, str | None]:
    """
    Confidence-based and multi-signal gating. Returns (allowed, reason_if_blocked).
    Context may include: confidence, baseline_confidence, flagged_metric_count, persistence_cycles.
    """
    auth = policy.decision_authority or {}
    if not auth:
        return True, None
    min_conf = auth.get("min_confidence")
    min_baseline = auth.get("min_baseline_confidence")
    min_metrics = auth.get("min_metrics_for_critical", 2)
    min_persistence = auth.get("time_persistence_cycles", 0)
    confidence = context.get("confidence")
    if min_conf is not None and confidence is not None and confidence < min_conf:
        return False, "confidence_below_min"
    baseline_conf = context.get("baseline_confidence")
    if min_baseline is not None and baseline_conf is not None and baseline_conf < min_baseline:
        return False, "baseline_confidence_below_min"
    if action_type in SAFETY_CRITICAL_ACTIONS:
        flagged = context.get("flagged_metric_count", 0)
        if flagged < min_metrics:
            return False, "multi_signal_not_met"
        if min_persistence and context.get("persistence_cycles", 0) < min_persistence:
            return False, "time_persistence_not_met"
    # Fail-safe: when timing cannot be met, no dangerous actions (no shutdown/abort)
    fail_safe = context.get("fail_safe") or (
        getattr(policy, "fail_safe_on_timing", False) and not context.get("timing_slo_met", True)
    )
    if fail_safe and action_type in SAFETY_CRITICAL_ACTIONS:
        return False, "fail_safe_on_timing"
    # Baseline confidence coupling: block Tier 3 (critical) if baseline_confidence below min
    min_bc_critical = getattr(policy, "min_baseline_confidence_for_critical", 0) or 0
    if min_bc_critical > 0 and action_type in SAFETY_CRITICAL_ACTIONS:
        bc = context.get("baseline_confidence")
        if bc is not None and bc < min_bc_critical:
            return False, "baseline_confidence_below_min_for_critical"
    return True, None


def _tier_for_action(action_type: str, action_spec: dict) -> int:
    """Resolve tier from action_spec or ACTION_TIER_BY_TYPE."""
    t = action_spec.get("tier")
    if t is not None:
        return int(t)
    return ACTION_TIER_BY_TYPE.get(action_type, 1)


def _tier_allowed(policy: ActionPolicy, action_tier: int, context: dict) -> tuple[bool, str | None]:
    """Enforce max_allowed_tier and 2-man rule for Tier 3. Returns (allowed, reason_if_denied)."""
    max_tier = getattr(policy, "max_allowed_tier", None)
    if max_tier is not None and action_tier > max_tier:
        return False, "tier_above_max_allowed"
    if action_tier >= 3 and getattr(policy, "require_two_man_for_tier3", True):
        if not context.get("approval_token") and not context.get("second_approver_id"):
            return False, "tier3_requires_two_man_rule"
        if context.get("persistence_cycles", 0) < (policy.decision_authority or {}).get("time_persistence_cycles", 0):
            return False, "tier3_persistence_not_met"
    return True, None


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
        Return list of actions that would be executed (type, params, safety_gate_passed,
        action_allowed, confidence, baseline_confidence). Does not execute; use for dry-run.
        """
        context = context or {}
        independent_conditions = independent_conditions or []
        confidence = context.get("confidence")
        baseline_confidence = context.get("baseline_confidence")
        # Safe mode: no Tier 3, only notify (trigger on SLO breach, baseline collapse, instability)
        hb_mode = context.get("hb_mode") or getattr(self.policy, "hb_mode", "normal")
        safe_mode = (hb_mode or "").strip().lower() == "safe"
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
                action_tier = _tier_for_action(action_type, action_spec)
                if safe_mode and action_type != "notify":
                    out.append({
                        "type": action_type,
                        "params": action_spec.get("params") or {},
                        "tier": action_tier,
                        "safety_gate_passed": False,
                        "action_allowed": False,
                        "block_reason": "safe_mode_only_notify",
                        "confidence": confidence,
                        "baseline_confidence": baseline_confidence,
                        "would_execute": False,
                    })
                    continue
                tier_ok, tier_reason = _tier_allowed(self.policy, action_tier, context)
                if not tier_ok:
                    out.append({
                        "type": action_type,
                        "params": action_spec.get("params") or {},
                        "tier": action_tier,
                        "safety_gate_passed": False,
                        "action_allowed": False,
                        "block_reason": tier_reason,
                        "confidence": confidence,
                        "baseline_confidence": baseline_confidence,
                        "would_execute": False,
                    })
                    continue
                safety_ok = _safety_gate_passed(
                    self.policy, action_type, context, independent_conditions
                )
                action_ok, block_reason = _action_allowed(self.policy, action_type, context)
                action_allowed = safety_ok and action_ok
                out.append({
                    "type": action_type,
                    "params": action_spec.get("params") or {},
                    "tier": action_tier,
                    "safety_gate_passed": safety_ok,
                    "action_allowed": action_allowed,
                    "block_reason": None if action_allowed else (block_reason or "safety_gate_not_passed"),
                    "confidence": confidence,
                    "baseline_confidence": baseline_confidence,
                    "would_execute": action_allowed,
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
            decision = status
            confidence = item.get("confidence")
            baseline_confidence = item.get("baseline_confidence")
            action_allowed = item.get("action_allowed", item.get("safety_gate_passed", True))
            if dry_run:
                results.append({
                    "action_id": action_id,
                    "type": item["type"],
                    "decision": decision,
                    "confidence": confidence,
                    "baseline_confidence": baseline_confidence,
                    "action_allowed": action_allowed,
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
                    "decision": decision,
                    "confidence": confidence,
                    "baseline_confidence": baseline_confidence,
                    "action_allowed": False,
                    "status": "blocked",
                    "reason": "safety_gate_not_passed",
                    "dry_run": False,
                    "safety_gate_passed": False,
                })
                continue
            if not action_allowed:
                results.append({
                    "action_id": action_id,
                    "type": item["type"],
                    "decision": decision,
                    "confidence": confidence,
                    "baseline_confidence": baseline_confidence,
                    "action_allowed": False,
                    "status": "blocked",
                    "reason": item.get("block_reason") or "confidence_gate",
                    "dry_run": False,
                    "safety_gate_passed": item["safety_gate_passed"],
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
                    payload={"params": item["params"], "decision": status, "confidence": item.get("confidence"), "baseline_confidence": item.get("baseline_confidence"), "action_allowed": True, **context},
                    run_id=run_id,
                    decision_id=decision_id,
                    idempotency_key=idempotency_key,
                    safety_gate_passed=True,
                    dry_run=0,
                )
            results.append({
                "action_id": action_id,
                "type": item["type"],
                "decision": status,
                "confidence": item.get("confidence"),
                "baseline_confidence": item.get("baseline_confidence"),
                "action_allowed": True,
                "status": "pending",
                "dry_run": False,
                "safety_gate_passed": True,
            })
        return results


def execute_actions(
    status: str,
    context: dict | None = None,
    independent_conditions: list[dict] | None = None,
    policy_path: str | None = None,
    dry_run: bool = False,
    idempotency_key: str | None = None,
    conn=None,
    run_id: str | None = None,
    decision_id: str | None = None,
) -> list[dict]:
    """
    Convenience: create engine, execute, return results.
    Pass context with confidence, baseline_confidence, flagged_metric_count, persistence_cycles
    for decision-authority gating. Pass independent_conditions for safety gate (e.g. two conditions).
    """
    engine = ActionEngine(policy_path=policy_path)
    return engine.execute(
        status=status,
        context=context,
        independent_conditions=independent_conditions or [],
        dry_run=dry_run,
        idempotency_key=idempotency_key,
        conn=conn,
        run_id=run_id,
        decision_id=decision_id,
    )
