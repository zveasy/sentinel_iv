import copy
import os
import yaml

from hb.registry_utils import build_alias_index
from hb_core.compare import ComparePlan

_registry_cache = {}
_compare_plan_cache = {}

_DEFAULT_CONTEXT_MATCH = [
    "scenario_id",
    "operating_mode",
    "environment",
    "environment_fingerprint",
    "sensor_config_id",
    "input_data_version",
]


def _normalize_baseline_policy(payload):
    policy = payload.get("baseline_policy", payload) if isinstance(payload, dict) else {}
    policy = dict(policy or {})
    policy.setdefault("strategy", "last_pass")
    policy.setdefault("fallback", "latest")
    policy.setdefault("warn_on_mismatch", True)
    policy.setdefault("distribution_drift_enabled", True)
    policy.setdefault("context_match", list(_DEFAULT_CONTEXT_MATCH))
    governance = dict(policy.get("governance") or {})
    governance.setdefault("require_approval", False)
    governance.setdefault("approvals_required", 1)
    governance.setdefault("approvers", [])
    policy["governance"] = governance
    return policy


def _validate_baseline_policy(policy):
    if not isinstance(policy, dict):
        raise ValueError("baseline_policy must be a mapping")
    if policy.get("strategy") not in {"last_pass", "tag", "explicit"}:
        raise ValueError("baseline_policy.strategy must be one of: last_pass, tag, explicit")
    if policy.get("fallback") not in {"latest", "none"}:
        raise ValueError("baseline_policy.fallback must be one of: latest, none")
    context_match = policy.get("context_match")
    if not isinstance(context_match, list) or not context_match:
        raise ValueError("baseline_policy.context_match must be a non-empty list")
    governance = policy.get("governance") or {}
    if not isinstance(governance, dict):
        raise ValueError("baseline_policy.governance must be a mapping")
    approvals_required = governance.get("approvals_required", 1)
    if not isinstance(approvals_required, int) or approvals_required < 1:
        raise ValueError("baseline_policy.governance.approvals_required must be >= 1")
    return policy


def _normalize_metric_registry(payload):
    registry = dict(payload or {})
    registry.setdefault("version", "1.0")
    metrics = registry.get("metrics") or {}
    registry["metrics"] = metrics
    registry.setdefault("programs", {})
    return registry


def _validate_metric_registry(registry):
    if not isinstance(registry, dict):
        raise ValueError("metric_registry must be a mapping")
    metrics = registry.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("metric_registry.metrics must be a non-empty mapping")
    for name, config in metrics.items():
        if not isinstance(config, dict):
            raise ValueError(f"metric config for {name} must be a mapping")
        aliases = config.get("aliases")
        if aliases is not None and not isinstance(aliases, list):
            raise ValueError(f"metric {name} aliases must be a list")
        for field in ("drift_threshold", "drift_percent", "min_effect", "fail_threshold"):
            if field in config and not isinstance(config.get(field), (int, float)):
                raise ValueError(f"metric {name} {field} must be numeric")
        for field in ("invariant_eq", "invariant_min", "invariant_max"):
            if field in config and not isinstance(config.get(field), (int, float)):
                raise ValueError(f"metric {name} {field} must be numeric")
        if config.get("critical"):
            if not any(field in config for field in ("invariant_eq", "invariant_min", "invariant_max")):
                raise ValueError(f"critical metric {name} must define an invariant_* constraint")
    programs = registry.get("programs", {})
    if programs and not isinstance(programs, dict):
        raise ValueError("metric_registry.programs must be a mapping")
    return registry


def _apply_program_overrides(registry, program):
    if not program:
        return registry
    programs = registry.get("programs") or {}
    overrides = programs.get(program)
    if not overrides:
        return registry
    merged = copy.deepcopy(registry)
    metrics = merged.get("metrics") or {}
    for metric, config in (overrides.get("metrics") or {}).items():
        base = dict(metrics.get(metric) or {})
        base.update(config or {})
        metrics[metric] = base
    merged["metrics"] = metrics
    return merged


def load_metric_registry(path, program=None):
    program = program or os.environ.get("HB_PROGRAM")
    cache_key = (path, program)
    mtime = os.path.getmtime(path)
    cached = _registry_cache.get(cache_key)
    if cached and cached["mtime"] == mtime:
        return cached["registry"]
    with open(path, "r") as f:
        registry = yaml.safe_load(f) or {}
    registry = _normalize_metric_registry(registry)
    registry = _apply_program_overrides(registry, program)
    _validate_metric_registry(registry)
    registry["alias_index"] = build_alias_index(registry)
    _registry_cache[cache_key] = {"mtime": mtime, "registry": registry}
    return registry


def load_compare_plan(path, program=None):
    program = program or os.environ.get("HB_PROGRAM")
    cache_key = (path, program)
    mtime = os.path.getmtime(path)
    cached = _compare_plan_cache.get(cache_key)
    if cached and cached["mtime"] == mtime:
        return cached["plan"]
    registry = load_metric_registry(path, program=program)
    plan = ComparePlan.compile(registry)
    _compare_plan_cache[cache_key] = {"mtime": mtime, "plan": plan}
    return plan


def load_baseline_policy(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f) or {}
    policy = _normalize_baseline_policy(payload)
    return _validate_baseline_policy(policy)
