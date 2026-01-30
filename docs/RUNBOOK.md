# DoD Lab Runbook

## Daily Operations
- Run `bin/hb run` for each new test export.
- Confirm report output in `mvp/reports/<run_id>/`.
- Review `drift_report.json` and `drift_report.html`.

## Baseline Governance
- Tag a baseline: `bin/hb baseline set <run_id> --tag golden`
- List baselines: `bin/hb baseline list`
- Baseline selection uses last PASS unless a tag is set in `baseline_policy.yaml`.

## Auditability
- `artifact_manifest.json` records hashes for report artifacts.
- `audit_log.jsonl` records analysis actions.
- Verify signatures: `bin/hb verify --report-dir mvp/reports/<run_id> --sign-key keys/signing.key`

## Diagnostics
- Health check: `bin/hb support health`
- Support bundle: `bin/hb support bundle --report-dir mvp/reports/<run_id>`
- Heartbeat: `bin/hb monitor heartbeat` (writes to `artifacts/heartbeat.jsonl`)

## Backup & Retention
- Backup registry: `tools/backup_registry.sh runs.db backups`
- Prune reports: `python tools/retention_prune.py --policy retention_policy.yaml --db runs.db`
- If using SQLCipher: encrypt/decrypt via `bin/hb db encrypt/decrypt`.

## Incident Recovery
- Restore `runs.db` from the latest backup.
- Re-run analyses as needed to regenerate reports.
- Verify integrity with manifests and signatures.
- Follow `docs/INCIDENT_RESPONSE.md` for field incidents.
