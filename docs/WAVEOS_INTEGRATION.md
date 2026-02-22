# WaveOS Integration (Design Placeholder)

Harmony Bridge is intended to integrate with the WaveOS ecosystem as a platform product. This document captures the planned integration contract and event schema. **Implementation is not yet in scope**; this is a design placeholder for a future sprint.

## Goals

- **HB → WaveOS:** HB publishes health/drift events so WaveOS can display dashboards, route alerts, and enforce policy.
- **WaveOS → HB:** WaveOS sends policy updates (e.g. baseline tags, threshold overrides) that HB enforces for subsequent runs.

## Planned API Contract

| Direction | Description |
|-----------|-------------|
| HB → WaveOS | HB emits **health events** (e.g. on drift/FAIL): run_id, status, primary_issue, report path, severity. Transport: webhook, message bus, or shared event log. |
| WaveOS → HB | WaveOS sends **policy updates**: baseline tag to use, optional threshold overrides, allowlist for metrics. HB reloads config or applies updates for the next run. |

## Event Schema

- A **shared JSON schema** is in `schemas/waveos_events.json`:
  - **Health event:** `ts`, `source`, `run_id`, `status`, `severity`, `primary_issue`, `report_path`, `drift_metrics[]`.
  - **Policy update:** `ts`, `baseline_tag`, `threshold_overrides`, `metric_allowlist`.
- Extend or replace as needed when implementing the WaveOS adapter.

## Adapter Module

- **`hb/adapters/waveos.py`** implements:
  - **`publish_health_event(webhook_url, event)`** — POSTs a health event (ts, source, run_id, status, severity, primary_issue, report_path, drift_metrics) to a WaveOS webhook. Use from daemon or after analyze to push drift/FAIL events.
  - **`apply_policy_update(update)`** — Accepts a policy update (baseline_tag, threshold_overrides, metric_allowlist) and returns what would be applied; callers can persist to baseline_policy or metric_registry.
- To push events from the daemon, set a webhook URL in config and call `publish_health_event` when status is FAIL or PASS_WITH_DRIFT (or use the existing alert webhook sink with WaveOS endpoint).
- Authentication: add headers (e.g. API key) via the `headers` argument to `publish_health_event`; mTLS would require a custom opener (document in security posture).

## References

- Internal: `docs/THREAT_MODEL_CUSTOMER.md`, `docs/FIELD_DEPLOYMENT_V1.md`.
- Pilot sprint: `docs/PILOT_2WEEK_SPRINT.md` (WaveOS is out of scope for the 2-week pilot).
