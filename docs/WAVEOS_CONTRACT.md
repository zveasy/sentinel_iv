# WaveOS Integration Contract

Formal event contract between Harmony Bridge and WaveOS.

## HB → WaveOS (emitted by HB)

| Event | Description |
|-------|-------------|
| **HEALTH_EVENT** | Current health summary (status, baseline match, top drift). |
| **DRIFT_EVENT** | Drift or failure detected (run_id, status, drift_metrics, report_path). |
| **ACTION_REQUEST** | Request for WaveOS to perform an action (e.g. degrade mode, apply policy). |

Payload shape: see `schemas/waveos_events.json` and `hb/adapters/waveos.py` (`publish_health_event`, etc.).

## WaveOS → HB (responses / callbacks)

| Event | Description |
|-------|-------------|
| **ACTION_ACK** | Acknowledgment of an action request (action_id, status, message). |
| **MODE_CHANGED** | Operational mode was changed (from_mode, to_mode, reason). |
| **POLICY_APPLIED** | Policy update was applied (policy_id, version). |

HB can consume these (e.g. via webhook or poll) to update state or audit.

## Rate limiting and rollout

- **Rate-limited policy updates:** When HB sends policy updates to WaveOS, limit frequency (e.g. max one per minute) and use a queue or backoff on NACK.
- **Staged rollout:** Prefer applying policy to a subset of nodes first; WaveOS returns POLICY_APPLIED when done.
- **Rollback:** WaveOS should support reverting to a previous policy version; HB can send ACTION_REQUEST with rollback params.

## Policy provenance

- Record who/what requested policy changes (operator_id, reason, timestamp) in HB audit or action ledger.
- When WaveOS returns POLICY_APPLIED, log it with the policy version and source (HB run_id or request_id).
