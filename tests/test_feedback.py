import json

import pytest

from hb import feedback


def test_feedback_logging_and_export(tmp_path):
    log_path = tmp_path / "feedback.jsonl"
    record = {
        "hb_version": "dev",
        "source_type": "pba_excel",
        "metric": "avg_latency_ms",
        "decision": "PASS_WITH_DRIFT",
        "top_driver": "avg_latency_ms",
        "effect_size": 0.2,
        "thresholds": {"warn": 1.0, "percent": 10.0, "persistence": 5},
        "operator_action": "accepted",
    }
    feedback.write_feedback_record(record, log_path=str(log_path))

    summary = feedback.export_feedback(str(log_path), None, mode="summary")
    assert summary["count"] == 1
    assert summary["by_metric"]["avg_latency_ms"] == 1
    assert summary["by_action"]["accepted"] == 1

    raw = feedback.export_feedback(str(log_path), None, mode="raw")
    assert raw["count"] == 1
    assert raw["records"][0]["metric"] == "avg_latency_ms"


def test_feedback_export_invalid_mode(tmp_path):
    log_path = tmp_path / "feedback.jsonl"
    log_path.write_text(json.dumps({"metric": "x"}) + "\n")
    with pytest.raises(ValueError, match="invalid export mode"):
        feedback.export_feedback(str(log_path), None, mode="bad")
