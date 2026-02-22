"""
Determinism tests: same input + config -> same decision (fixed seed where applicable).
"""
import os
import random

import pytest

from hb.engine import compare_metrics, normalize_metrics
from hb.registry_utils import build_alias_index


def test_compare_metrics_deterministic():
    """Same current, baseline, registry -> same status and drift list."""
    registry = {
        "metrics": {
            "m1": {"drift_threshold": 1.0, "unit": ""},
            "m2": {"drift_percent": 10.0, "unit": ""},
        },
        "alias_index": build_alias_index({"metrics": {"m1": {}, "m2": {}}}),
    }
    current = {"m1": {"value": 10.0, "unit": "", "tags": ""}, "m2": {"value": 100.0, "unit": "", "tags": ""}}
    baseline = {"m1": {"value": 10.0, "unit": "", "tags": ""}, "m2": {"value": 100.0, "unit": "", "tags": ""}}

    r1 = compare_metrics(current, baseline, registry, distribution_enabled=False, plan=None, early_exit=False, deterministic=True)
    r2 = compare_metrics(current, baseline, registry, distribution_enabled=False, plan=None, early_exit=False, deterministic=True)
    assert r1[0] == r2[0]
    assert len(r1[1]) == len(r2[1])
    assert r1[2] == r2[2]


def test_compare_metrics_drift_deterministic():
    """With drift, result is still deterministic."""
    registry = {
        "metrics": {"m1": {"drift_threshold": 1.0, "unit": ""}},
        "alias_index": build_alias_index({"metrics": {"m1": {}}}),
    }
    current = {"m1": {"value": 12.0, "unit": "", "tags": ""}}
    baseline = {"m1": {"value": 10.0, "unit": "", "tags": ""}}

    r1 = compare_metrics(current, baseline, registry, distribution_enabled=False, plan=None, early_exit=False, deterministic=True)
    r2 = compare_metrics(current, baseline, registry, distribution_enabled=False, plan=None, early_exit=False, deterministic=True)
    assert r1[0] == r2[0] == "PASS_WITH_DRIFT"
    assert r1[1] == r2[1]
