"""
Golden test for compare_metrics: same inputs must produce expected status and drift set.
"""
import json
import os

import pytest

from hb.config import _normalize_metric_registry
from hb.engine import compare_metrics


def _load_golden():
    path = os.path.join(os.path.dirname(__file__), "golden", "compare_expected.json")
    with open(path) as f:
        return json.load(f)


def _registry_from_metrics(metrics_config):
    """Build minimal metric_registry dict from metrics config."""
    alias_index = {}
    metrics = {}
    for name, cfg in metrics_config.items():
        alias_index[name] = name
        alias_index[name.lower()] = name
        metrics[name] = dict(cfg)
    return _normalize_metric_registry({"alias_index": alias_index, "metrics": metrics})


def test_golden_compare():
    golden = _load_golden()
    inputs = golden["inputs"]
    expected = golden["expected"]
    baseline = inputs["baseline"]
    current = inputs["current"]
    registry = _registry_from_metrics(inputs["registry_metrics"])

    status, drift, warnings, fail, inv, dist_drift, attribution = compare_metrics(
        current, baseline, registry, distribution_enabled=False, plan=None
    )

    assert status == expected["status"], (status, drift)
    drift_names = sorted([d["metric"] for d in drift])
    assert drift_names == sorted(expected["drift_metric_names"]), (drift_names, expected["drift_metric_names"])
    fail_names = sorted([f["metric"] for f in fail])
    assert fail_names == sorted(expected["fail_metric_names"]), (fail_names, expected["fail_metric_names"])
    assert len(warnings) == expected["num_warnings"], (warnings, expected["num_warnings"])
