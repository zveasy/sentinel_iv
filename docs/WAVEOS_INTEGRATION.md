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

## Event Schema (TODO)

- Define a **shared JSON schema** (or `.proto`) for:
  - Health event: `ts`, `source`, `run_id`, `status`, `severity`, `primary_issue`, `report_path`, `drift_metrics[]`.
  - Policy update: `ts`, `baseline_tag`, `threshold_overrides`, `metric_allowlist`.
- Location: e.g. `schemas/waveos_events.json` or a shared repo.

## Adapter Module (TODO)

- Implement a **WaveOS adapter** module (e.g. `hb/adapters/waveos.py` or `waveos_adapter/`) that:
  - Subscribes to or receives policy updates from WaveOS.
  - Publishes health events to WaveOS (webhook or message bus).
- Authentication: mTLS or API key; document in security posture.

## References

- Internal: `docs/THREAT_MODEL_CUSTOMER.md`, `docs/FIELD_DEPLOYMENT_V1.md`.
- Pilot sprint: `docs/PILOT_2WEEK_SPRINT.md` (WaveOS is out of scope for the 2-week pilot).
