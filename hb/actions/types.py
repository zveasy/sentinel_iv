"""
Policy-driven action types: notify, degrade, failover, abort, isolate, rate_limit, shutdown.
"""
# Action type -> description; execution is pluggable per type
ACTION_TYPES = {
    "notify": "Send notification (e.g. webhook, email, alert sink)",
    "degrade": "Signal degradation mode (e.g. reduce fidelity, disable non-critical)",
    "failover": "Trigger failover to standby",
    "abort": "Abort current operation / test",
    "isolate": "Isolate subsystem or segment",
    "rate_limit": "Apply or tighten rate limit",
    "shutdown": "Orderly shutdown (hard shutdown requires safety gate)",
}

# Actions that require two independent conditions (safety gate) before execution
SAFETY_CRITICAL_ACTIONS = {"shutdown", "abort"}
