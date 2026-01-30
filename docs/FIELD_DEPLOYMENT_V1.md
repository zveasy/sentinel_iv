# Field Deployment v1 (Microgrid + EV Chargers)

Minimum production requirements beyond the core HB checklist:

1) Safety case + hazard analysis (FMEA/FTA) for control actions.
2) Guardrails config enforced for all actions (rate limits, restart budgets, safe-mode bounds).
3) Human-in-the-loop approvals and rollback procedures.
4) Monitoring + incident response runbooks.
5) Security posture: secrets, auth, segmentation, key rotation.
6) Staged rollout gates with explicit acceptance criteria.

Recommended tooling in this repo:
- Guardrails check: `python tools/guardrails_check.py --action <action.json>`
- Rollout gates: `python tools/rollout_check.py --config configs/rollout_gates.yaml`
- Health check: `bin/hb support health`
- Support bundle: `bin/hb support bundle --report-dir mvp/reports/<run_id>`
- Heartbeat log: `bin/hb monitor heartbeat`

Reference docs:
- `docs/SAFETY_CASE_TEMPLATE.md`
- `docs/ROLLBACK_PROCEDURE.md`
- `docs/INCIDENT_RESPONSE.md`
- `docs/SECURITY_POSTURE.md`
