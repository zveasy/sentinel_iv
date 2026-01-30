# Incident Response (Field Deployment)

## Triggers
- Uncommanded load shedding, charger brownouts, or safety trip events.
- Repeated failed actions or policy oscillation.
- Loss of telemetry or sensor integrity.

## Immediate Actions
1) Switch to safe mode (manual override).
2) Freeze automated actions.
3) Capture evidence (logs, reports, support bundle).

## Recovery
1) Validate baseline integrity.
2) Re-run analysis on latest telemetry.
3) Approve rollback or controlled re-enable.

## Evidence Pack
- `support_bundle.zip`
- `perf.json`
- `audit_log.jsonl`
- `artifact_manifest.json`
