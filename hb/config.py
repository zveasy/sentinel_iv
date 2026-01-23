import yaml

from hb.registry_utils import build_alias_index


def load_metric_registry(path):
    with open(path, "r") as f:
        registry = yaml.safe_load(f)
    registry["alias_index"] = build_alias_index(registry)
    return registry


def load_baseline_policy(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f)
    return payload.get("baseline_policy", payload)
