"""
WaveOS adapter: publish health events to WaveOS (webhook) and accept policy updates.
See docs/WAVEOS_INTEGRATION.md and schemas/waveos_events.json.
"""
import json
import urllib.request
from datetime import datetime, timezone
from typing import Any


def publish_health_event(
    webhook_url: str,
    event: dict[str, Any],
    timeout_sec: float = 10.0,
    headers: dict[str, str] | None = None,
) -> bool:
    """
    POST a health event to the WaveOS webhook. Event should match schemas/waveos_events.json
    health_event: ts, source, run_id, status, severity, primary_issue, report_path, drift_metrics.
    Returns True if POST succeeded (2xx), False otherwise.
    """
    if not event.get("ts"):
        event = {**event, "ts": datetime.now(timezone.utc).isoformat()}
    if not event.get("source"):
        event = {**event, "source": "harmony_bridge"}
    data = json.dumps(event).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(webhook_url, data=data, method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def apply_policy_update(update: dict[str, Any], baseline_policy_path: str | None = None) -> dict[str, Any]:
    """
    Apply a policy update from WaveOS (baseline_tag, threshold_overrides, metric_allowlist).
    Returns a summary of what would be or was applied. This implementation returns the
    suggested changes; callers can write to baseline_policy or metric_registry as needed.
    """
    applied = {}
    if update.get("baseline_tag"):
        applied["baseline_tag"] = update["baseline_tag"]
    if update.get("threshold_overrides"):
        applied["threshold_overrides"] = update["threshold_overrides"]
    if update.get("metric_allowlist"):
        applied["metric_allowlist"] = update["metric_allowlist"]
    return applied
