"""
Baseline equivalence mapping: vendor A <-> vendor B (sensor name/scale).
Apply in compare when baseline is from a different platform.
"""
import os
from typing import Any

import yaml


def load_equivalence_mapping(path: str | None = None) -> dict:
    if path is None:
        path = os.environ.get("HB_EQUIVALENCE_MAPPING", "config/equivalence_mapping.yaml")
    if not path or not os.path.isfile(path):
        return {"version": "1.0", "mappings": []}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {"version": "1.0", "mappings": []}


def apply_equivalence(
    metrics: dict[str, Any],
    mapping: dict | None = None,
    source_platform: str | None = None,
    target_platform: str | None = None,
) -> dict[str, Any]:
    """
    Map baseline metrics (source_platform) to current platform (target_platform) using mapping.
    Each mapping entry: { source_name, target_name?, scale?, offset?, unit_map? }.
    If source_platform/target_platform given, only apply mappings for that pair.
    """
    if mapping is None:
        mapping = load_equivalence_mapping()
    mappings = mapping.get("mappings") or []
    out = {}
    for m in metrics:
        val = metrics[m].get("value") if isinstance(metrics[m], dict) else metrics[m]
        unit = metrics[m].get("unit") if isinstance(metrics[m], dict) else ""
        tags = metrics[m].get("tags") if isinstance(metrics[m], dict) else None
        target_name = m
        scale = 1.0
        offset = 0.0
        for rule in mappings:
            if rule.get("source_name") != m:
                continue
            if source_platform and rule.get("source_platform") and rule["source_platform"] != source_platform:
                continue
            if target_platform and rule.get("target_platform") and rule["target_platform"] != target_platform:
                continue
            target_name = rule.get("target_name") or m
            scale = float(rule.get("scale", 1.0))
            offset = float(rule.get("offset", 0.0))
            break
        try:
            v = float(val) if val is not None else None
            if v is not None:
                v = v * scale + offset
        except (TypeError, ValueError):
            v = val
        out[target_name] = {"value": v, "unit": unit, "tags": tags}
    return out
