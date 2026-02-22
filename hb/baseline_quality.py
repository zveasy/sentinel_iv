"""
Baseline quality gates: acceptance criteria and confidence score (0-1).
Used to block tagging low-quality baselines and in decisions (e.g. don't enforce hard actions with low confidence).
"""
import os
from typing import Any

import yaml


def load_baseline_quality_policy(path: str | None = None) -> dict:
    if path is None:
        path = os.environ.get("HB_BASELINE_QUALITY_POLICY", "config/baseline_quality_policy.yaml")
    if not path or not os.path.isfile(path):
        return _default_policy()
    with open(path, "r") as f:
        return yaml.safe_load(f) or _default_policy()


def _default_policy() -> dict:
    return {
        "version": "1.0",
        "acceptance_criteria": {
            "min_sample_size": 10,
            "min_time_in_state_sec": 3600,
            "stability": {"max_coefficient_of_variation": 0.5, "exclude_metrics": []},
            "no_unresolved_alerts": True,
            "min_environment_match_score": 0.7,
        },
        "confidence_weights": {
            "sample_size": 0.2,
            "stability": 0.3,
            "no_alerts": 0.3,
            "environment_match": 0.2,
        },
    }


def evaluate_baseline_quality(
    sample_size: int,
    time_span_sec: float,
    stability_ok: bool,
    no_alerts: bool,
    environment_match_score: float,
    policy: dict | None = None,
) -> tuple[bool, float, list[str]]:
    """
    Evaluate baseline against acceptance criteria and compute confidence score (0-1).
    Returns (passed, confidence, list of failure reasons).
    """
    policy = policy or load_baseline_quality_policy()
    criteria = policy.get("acceptance_criteria") or {}
    weights = policy.get("confidence_weights") or {}
    reasons = []

    min_n = int(criteria.get("min_sample_size", 10))
    min_sec = float(criteria.get("min_time_in_state_sec", 3600))
    min_match = float(criteria.get("min_environment_match_score", 0.7))

    score_sample = 1.0 if sample_size >= min_n else min(1.0, sample_size / max(1, min_n))
    if sample_size < min_n:
        reasons.append(f"sample_size {sample_size} < {min_n}")

    score_time = 1.0 if time_span_sec >= min_sec else min(1.0, time_span_sec / max(1, min_sec))
    if time_span_sec < min_sec:
        reasons.append(f"time_span_sec {time_span_sec} < {min_sec}")

    score_stability = 1.0 if stability_ok else 0.0
    if not stability_ok:
        reasons.append("stability check failed")

    score_alerts = 1.0 if no_alerts else 0.0
    if criteria.get("no_unresolved_alerts") and not no_alerts:
        reasons.append("unresolved alerts in window")

    score_env = environment_match_score if 0 <= environment_match_score <= 1 else 0.0
    if environment_match_score < min_match:
        reasons.append(f"environment_match_score {environment_match_score} < {min_match}")

    w_sample = float(weights.get("sample_size", 0.2))
    w_stability = float(weights.get("stability", 0.3))
    w_alerts = float(weights.get("no_alerts", 0.3))
    w_env = float(weights.get("environment_match", 0.2))
    confidence = (
        score_sample * w_sample
        + score_stability * w_stability
        + score_alerts * w_alerts
        + score_env * w_env
        + score_time * 0.0  # time can be folded into sample in a richer model
    )
    confidence = max(0.0, min(1.0, confidence))

    passed = (
        sample_size >= min_n
        and time_span_sec >= min_sec
        and stability_ok
        and (no_alerts or not criteria.get("no_unresolved_alerts"))
        and environment_match_score >= min_match
    )
    return passed, confidence, reasons
