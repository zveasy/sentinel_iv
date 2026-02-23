"""
Composite decision confidence: drift magnitude, metric count, baseline confidence, historical accuracy.
"""
from typing import Any


def compute_decision_confidence(
    baseline_confidence: float | None = None,
    drift_magnitude: float | None = None,
    metric_count: int = 0,
    coverage: float = 1.0,
    historical_accuracy_30d: float | None = None,
    reduced_due_to_missing_data: bool = False,
) -> float:
    """
    Composite confidence in [0, 1]. Combines baseline, drift severity, coverage, optional historical.
    reduced_due_to_missing_data: if True, cap confidence (e.g. * 0.8).
    """
    base = float(baseline_confidence) if baseline_confidence is not None else 0.8
    # Drift severity: 0 = no drift -> 1, high drift -> lower
    drift_factor = 1.0
    if drift_magnitude is not None and drift_magnitude > 0:
        drift_factor = max(0.0, 1.0 - min(1.0, drift_magnitude))
    # Metric count: more metrics = slightly more confidence (bounded)
    count_factor = min(1.0, 0.7 + 0.3 * (min(metric_count, 50) / 50)) if metric_count else 1.0
    # Coverage
    cov = max(0.0, min(1.0, float(coverage)))
    # Weights
    w_base = 0.4
    w_drift = 0.25
    w_cov = 0.2
    w_hist = 0.15
    hist = float(historical_accuracy_30d) if historical_accuracy_30d is not None else 0.9
    raw = w_base * base + w_drift * drift_factor + w_cov * cov * count_factor + w_hist * hist
    raw = max(0.0, min(1.0, raw))
    if reduced_due_to_missing_data:
        raw = min(raw, 0.85)
    return round(raw, 2)


def drift_magnitude_from_report(report_payload: dict[str, Any]) -> float:
    """Extract a single drift magnitude from report (e.g. top driver score or 0)."""
    attribution = report_payload.get("drift_attribution") or {}
    top = (attribution.get("top_drivers") or [])
    if not top:
        return 0.0
    first = top[0]
    score = first.get("drift_score")
    if score is not None:
        return float(score)
    return 0.0
