"""
Baseline decay detection: baseline age + drift-from-current; alert when baseline no longer representative.
"""
from datetime import datetime, timezone, timedelta
from typing import Any


def parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def baseline_age_sec(baseline_created_at: str | None) -> float | None:
    """Return age of baseline in seconds, or None if unknown."""
    dt = parse_iso_utc(baseline_created_at)
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds()


def check_baseline_decay(
    baseline_created_at: str | None,
    baseline_metrics: dict,
    current_metrics: dict,
    max_age_sec: float = 86400 * 7,  # 7 days
    max_drift_fraction: float = 0.5,
    min_metrics: int = 3,
) -> tuple[bool, list[str]]:
    """
    Check if baseline is stale (decay). Returns (is_stale, list of reasons).
    - Age: baseline older than max_age_sec.
    - Drift-from-current: fraction of metrics that drift beyond threshold (simple count).
    """
    reasons = []
    if not baseline_metrics:
        return True, ["baseline has no metrics"]

    age = baseline_age_sec(baseline_created_at)
    if age is not None and age > max_age_sec:
        reasons.append(f"baseline age {age / 86400:.1f}d > max {max_age_sec / 86400:.1f}d")

    common = [m for m in baseline_metrics if m in current_metrics]
    if len(common) < min_metrics:
        reasons.append(f"too few common metrics ({len(common)} < {min_metrics})")
    else:
        drift_count = 0
        for m in common:
            bv = baseline_metrics[m].get("value")
            cv = current_metrics[m].get("value")
            if bv is None or cv is None:
                continue
            try:
                bf, cf = float(bv), float(cv)
            except (TypeError, ValueError):
                continue
            if bf == 0:
                if abs(cf) > 1e-9:
                    drift_count += 1
            elif abs((cf - bf) / bf) > max_drift_fraction:
                drift_count += 1
        fraction = drift_count / len(common) if common else 0
        if fraction >= 0.5:
            reasons.append(f"fraction of metrics drifting from current {fraction:.2f} >= 0.5")

    return len(reasons) > 0, reasons
