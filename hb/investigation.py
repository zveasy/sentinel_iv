"""
Build investigation hints and a direct "what to do next" summary from drift/fail data.
Helps users pinpoint the problem and suggested actions.
"""

from typing import Any, Dict, List, Optional


def _pinpoint_driver(driver: Dict[str, Any]) -> str:
    """One-sentence pinpoint for a single driver."""
    metric = driver.get("metric_name") or "metric"
    effect = driver.get("effect_size") or {}
    delta = effect.get("delta")
    percent = effect.get("percent")
    score_type = driver.get("score_type") or "delta"
    basis = driver.get("decision_basis") or []
    parts = [f"**{metric}**"]
    if "critical" in basis or "invariant" in str(basis).lower():
        parts.append("fails a critical or invariant rule")
    elif percent is not None:
        direction = "increased" if percent >= 0 else "decreased"
        parts.append(f"{direction} by {abs(round(percent, 2))}%")
        if delta is not None and delta != 0:
            parts.append(f" (absolute change: {round(delta, 4)})")
    elif delta is not None:
        direction = "above" if delta >= 0 else "below"
        parts.append(f"is {abs(round(delta, 4))} {direction} baseline")
    if driver.get("drift_percent") is not None:
        parts.append(f"| warn threshold: {driver.get('drift_percent')}%")
    elif driver.get("drift_threshold") is not None:
        parts.append(f"| warn threshold: {driver.get('drift_threshold')}")
    return " ".join(parts) + "."


def _suggested_actions_for_driver(
    driver: Dict[str, Any],
    metric_name_lower: str,
    status: str,
) -> List[str]:
    """Suggested next steps for one driver."""
    actions = []
    basis = driver.get("decision_basis") or []
    if "critical" in basis:
        actions.append("Treat as blocking: fix or justify before release.")
    if "invariant" in str(basis).lower() or "invariant_eq" in str(basis).lower():
        actions.append("Verify invariant rule in metric registry; fix value or relax rule if intentional.")
    if "distribution_ks" in basis:
        actions.append("Distribution changed (KS test). Review sample population and environment.")
    if status == "PASS_WITH_DRIFT" and "drift_threshold" in basis or "drift_percent" in basis:
        actions.append("If change is intentional, consider updating the baseline for this scenario.")
    if "latency" in metric_name_lower or "lag" in metric_name_lower:
        actions.append("Check runtime scheduling, queuing, and downstream latency.")
    if "error" in metric_name_lower or "failure" in metric_name_lower or "reset" in metric_name_lower:
        actions.append("Check transport reliability, schema validation, and upstream failures.")
    if "throughput" in metric_name_lower or "rate" in metric_name_lower or "qps" in metric_name_lower:
        actions.append("Check backpressure, rate limits, and queue depth.")
    if "deadline" in metric_name_lower or "missed_deadline" in metric_name_lower:
        actions.append("Check scheduler, task duration, and load; verify timing assumptions.")
    if "watchdog" in metric_name_lower:
        actions.append("Check watchdog configuration and health; verify no false triggers.")
    if "count" in metric_name_lower and ("reset" in metric_name_lower or "error" in metric_name_lower):
        actions.append("Check for repeated resets or error bursts; review logs around the event.")
    if not actions:
        actions.append("Review metric source and baseline context; adjust thresholds if needed.")
    return actions


def _root_cause_category(driver: Dict[str, Any]) -> str:
    """Label the kind of issue for this driver."""
    basis = driver.get("decision_basis") or []
    if "critical" in basis:
        return "critical_threshold"
    if any("invariant" in str(b).lower() for b in basis):
        return "invariant_violation"
    if "distribution_ks" in basis:
        return "distribution_shift"
    if "drift_threshold" in basis or "drift_percent" in basis:
        return "threshold_exceeded"
    return "drift_or_fail"


def root_cause_category_label(category: str) -> str:
    """Human-readable label for root_cause_category."""
    labels = {
        "critical_threshold": "Critical threshold exceeded",
        "invariant_violation": "Invariant violated",
        "distribution_shift": "Distribution shifted",
        "threshold_exceeded": "Drift threshold exceeded",
        "drift_or_fail": "Drift or fail",
    }
    return labels.get(category, category.replace("_", " ").title())


def build_investigation_hints(
    drift_attribution: List[Dict[str, Any]],
    fail_metrics: List[str],
    invariant_violations: List[Dict[str, Any]],
    status: str,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build investigation hints and a short "what to do next" summary.

    Returns:
        {
            "investigation_hints": [ {"metric", "pinpoint", "suggested_actions", "root_cause_category"} ],
            "what_to_do_next": "single paragraph summary",
            "primary_issue": "one line for the top issue",
        }
    """
    warnings = warnings or []
    investigation_hints = []
    primary_issue = None
    what_parts = []

    # Per-driver hints (top drivers only; avoid duplication with fail_metrics)
    seen_metrics = set()
    for driver in drift_attribution[:10]:
        name = driver.get("metric_name")
        if not name or name in seen_metrics:
            continue
        seen_metrics.add(name)
        name_lower = name.lower()
        pinpoint = _pinpoint_driver(driver)
        actions = _suggested_actions_for_driver(driver, name_lower, status)
        category = _root_cause_category(driver)
        investigation_hints.append({
            "metric": name,
            "pinpoint": pinpoint,
            "suggested_actions": actions,
            "root_cause_category": category,
            "root_cause_label": root_cause_category_label(category),
        })
        if primary_issue is None:
            primary_issue = pinpoint

    # Invariant violations not already in drivers
    for inv in invariant_violations:
        metric = inv.get("metric")
        if metric and metric not in seen_metrics:
            seen_metrics.add(metric)
        if not metric:
            continue
        inv_min = inv.get("invariant_min")
        inv_max = inv.get("invariant_max")
        inv_eq = inv.get("invariant_eq")
        current = inv.get("current")
        desc = f"**{metric}** violates invariant"
        if inv_eq is not None:
            desc += f" (expected {inv_eq}, got {current})"
        elif inv_min is not None or inv_max is not None:
            desc += f" (current {current}, allowed range: [{inv_min}, {inv_max}])"
        desc += "."
        investigation_hints.append({
            "metric": metric,
            "pinpoint": desc,
            "suggested_actions": ["Verify invariant in metric registry; fix value or relax rule if intentional."],
            "root_cause_category": "invariant_violation",
            "root_cause_label": root_cause_category_label("invariant_violation"),
        })
        if primary_issue is None:
            primary_issue = desc

    # Fail metrics not yet covered
    for metric in fail_metrics:
        if metric in seen_metrics:
            continue
        seen_metrics.add(metric)
        investigation_hints.append({
            "metric": metric,
            "pinpoint": f"**{metric}** exceeds fail (critical) threshold.",
            "suggested_actions": ["Treat as blocking; fix or justify before release."],
            "root_cause_category": "critical_threshold",
            "root_cause_label": root_cause_category_label("critical_threshold"),
        })
        if primary_issue is None:
            primary_issue = f"**{metric}** exceeds fail threshold."

    # Warnings that suggest missing data
    missing_warnings = [w for w in warnings if "missing" in w.lower()]
    if missing_warnings and primary_issue is None:
        primary_issue = "Missing metrics or data: " + "; ".join(missing_warnings[:3])
    if status == "NO_METRICS":
        what_parts.append("No metrics were evaluated. Check that inputs and metric registry align (column names, schema).")

    # Build "what to do next" paragraph
    if primary_issue:
        what_parts.append(f"Primary issue: {primary_issue}")
    if investigation_hints:
        first = investigation_hints[0]
        acts = first.get("suggested_actions") or []
        if acts:
            what_parts.append(f"Suggested next steps: {acts[0]}")
        if len(investigation_hints) > 1:
            what_parts.append(f"Plus {len(investigation_hints) - 1} other flagged metric(s)—see investigation hints below.")
    if missing_warnings and "missing" not in (what_parts[0] or ""):
        what_parts.append("Address missing-metric warnings so coverage is complete.")

    what_to_do_next = " ".join(what_parts) if what_parts else (
        "No drift or failures detected. If you expected changes, check baseline selection and registry."
    )

    return {
        "investigation_hints": investigation_hints,
        "what_to_do_next": what_to_do_next,
        "primary_issue": primary_issue,
    }
