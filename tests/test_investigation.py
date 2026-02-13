"""Tests for investigation hints and what_to_do_next."""

import pytest

from hb.investigation import build_investigation_hints, root_cause_category_label


def test_build_investigation_hints_drift():
    """Drift attribution produces pinpoint, suggested_actions, and what_to_do_next."""
    drift_attribution = [
        {
            "metric_name": "avg_latency_ms",
            "effect_size": {"delta": 2.0, "percent": 20.0},
            "decision_basis": ["drift_threshold", "drift_percent"],
            "drift_percent": 10.0,
            "drift_threshold": 1.0,
            "score_type": "percent",
        }
    ]
    out = build_investigation_hints(
        drift_attribution=drift_attribution,
        fail_metrics=[],
        invariant_violations=[],
        status="PASS_WITH_DRIFT",
        warnings=[],
    )
    assert "investigation_hints" in out
    assert "what_to_do_next" in out
    assert "primary_issue" in out
    assert len(out["investigation_hints"]) == 1
    h = out["investigation_hints"][0]
    assert h["metric"] == "avg_latency_ms"
    assert "avg_latency_ms" in h["pinpoint"]
    assert "20" in h["pinpoint"]
    assert h["root_cause_category"] == "threshold_exceeded"
    assert h["root_cause_label"] == "Drift threshold exceeded"
    assert len(h["suggested_actions"]) >= 1
    assert "Primary issue" in out["what_to_do_next"]
    assert "avg_latency_ms" in (out["primary_issue"] or "")


def test_build_investigation_hints_fail_metric():
    """Critical fail metric gets blocking suggested action."""
    out = build_investigation_hints(
        drift_attribution=[],
        fail_metrics=["watchdog_triggers"],
        invariant_violations=[],
        status="FAIL",
        warnings=[],
    )
    assert len(out["investigation_hints"]) == 1
    h = out["investigation_hints"][0]
    assert h["metric"] == "watchdog_triggers"
    assert "exceeds fail" in h["pinpoint"].lower()
    assert h["root_cause_category"] == "critical_threshold"
    assert any("blocking" in a.lower() for a in h["suggested_actions"])


def test_build_investigation_hints_invariant():
    """Invariant violation gets invariant hint."""
    out = build_investigation_hints(
        drift_attribution=[],
        fail_metrics=[],
        invariant_violations=[
            {"metric": "reset_count", "invariant_eq": 0, "current": 1}
        ],
        status="FAIL",
        warnings=[],
    )
    assert len(out["investigation_hints"]) == 1
    h = out["investigation_hints"][0]
    assert h["metric"] == "reset_count"
    assert "invariant" in h["pinpoint"].lower()
    assert h["root_cause_category"] == "invariant_violation"


def test_build_investigation_hints_pass_no_drift():
    """PASS with no drift yields no hints and generic what_to_do_next."""
    out = build_investigation_hints(
        drift_attribution=[],
        fail_metrics=[],
        invariant_violations=[],
        status="PASS",
        warnings=[],
    )
    assert len(out["investigation_hints"]) == 0
    assert out["primary_issue"] is None
    assert "No drift or failures" in out["what_to_do_next"]


def test_root_cause_category_label():
    assert root_cause_category_label("threshold_exceeded") == "Drift threshold exceeded"
    assert root_cause_category_label("invariant_violation") == "Invariant violated"
    assert root_cause_category_label("critical_threshold") == "Critical threshold exceeded"
    assert root_cause_category_label("unknown_foo") == "Unknown Foo"
