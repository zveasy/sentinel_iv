# Integration Checklist (Vendor‑Agnostic)

Use this checklist regardless of charger or microgrid controller vendor.

## 1) Interfaces + Protocols
- [ ] Confirm physical ports and cabling.
- [ ] Confirm protocol stack(s) and versions (OCPP/Modbus/DNP3/IEC‑61850/etc).
- [ ] Validate authentication method (certs/keys/tokens).

## 2) Telemetry
- [ ] Define required metrics list and units.
- [ ] Verify sampling rates and latency.
- [ ] Validate schema and normalization mapping.

## 3) Control Actions
- [ ] Enumerate allowed actions (rate limit, safe mode, restart, etc).
- [ ] Define guardrails (limits, TTLs, windows).
- [ ] Confirm control latency and ack behavior.

## 4) Safety + Fail‑Safe
- [ ] Manual override validated.
- [ ] Safe‑mode behavior verified.
- [ ] Rollback procedure tested.

## 5) Security
- [ ] Device identity provisioned.
- [ ] Network segmentation enforced.
- [ ] Audit logs + encrypted storage verified.

## 6) Monitoring + Ops
- [ ] Heartbeat/health checks wired.
- [ ] Incident response runbook ready.
- [ ] Support bundle generated and validated.

## 7) Rollout Gates
- [ ] All gates pass (`tools/rollout_check.py`).
- [ ] Pilot completed with acceptance criteria met.
- [ ] Final approval recorded.

