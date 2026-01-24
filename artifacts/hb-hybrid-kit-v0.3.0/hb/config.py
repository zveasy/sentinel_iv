import os
import yaml

from hb.registry_utils import build_alias_index
from hb_core.compare import ComparePlan

_registry_cache = {}
_compare_plan_cache = {}


def load_metric_registry(path):
    mtime = os.path.getmtime(path)
    cached = _registry_cache.get(path)
    if cached and cached["mtime"] == mtime:
        return cached["registry"]
    with open(path, "r") as f:
        registry = yaml.safe_load(f)
    registry["alias_index"] = build_alias_index(registry)
    _registry_cache[path] = {"mtime": mtime, "registry": registry}
    return registry


def load_compare_plan(path):
    mtime = os.path.getmtime(path)
    cached = _compare_plan_cache.get(path)
    if cached and cached["mtime"] == mtime:
        return cached["plan"]
    registry = load_metric_registry(path)
    plan = ComparePlan.compile(registry)
    _compare_plan_cache[path] = {"mtime": mtime, "plan": plan}
    return plan


def load_baseline_policy(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f)
    return payload.get("baseline_policy", payload)
