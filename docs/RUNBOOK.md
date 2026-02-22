# DoD Lab Runbook

## Daily Operations
- Run `bin/hb run` for each new test export.
- Confirm report output in `mvp/reports/<run_id>/`.
- Review `drift_report.json` and `drift_report.html`.

## Baseline Governance
- Tag a baseline: `bin/hb baseline set <run_id> --tag golden`
- List baselines: `bin/hb baseline list`
- Baseline selection uses `baseline_policy.yaml`: strategy can be `last_pass`, `tag`, `golden`, or `rolling` (see file comments).
- **Approval workflow (optional):** When `governance.require_approval` is true, use `hb baseline request` and `hb baseline approve`; approvers must be listed in `governance.approvers`. Document your internal SLA for approval in this runbook.
- **Time-window baseline:** `hb baseline create --window 24h` then `hb baseline promote --version <id> --tag golden`. Use `hb baseline versions` to list.

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

## Actions and operational mode
- **Actions (closed loop):** Policy in `config/actions_policy.yaml`. Execute: `hb actions execute --status FAIL` (or PASS_WITH_DRIFT). Use `--dry-run` to see what would run. List/ack: `hb actions list`, `hb actions ack --action-id <id>`.
- **Operational mode:** Set `operating_mode` in run_meta (e.g. nominal, degraded). Mode-aware thresholds use `metric_registry.mode_overrides`. Mode transitions: see `hb/modes.py` and audit with `transition_evidence()`.

## Baseline quality and decay
- **Quality gate:** `hb baseline set` runs baseline quality checks unless `--skip-quality-gate`. Configure in `config/baseline_quality_policy.yaml`; set `require_quality_gate: true` to block low-confidence baselines.
- **Decay:** Use `hb.baseline_decay.check_baseline_decay()` (or a CLI wrapper) to alert when baseline is stale (age or drift-from-current). Act on alerts by creating a new baseline or promoting a rolling version.

## Evidence pack (daemon)
- **On FAIL:** With `evidence_pack_on_fail: true` (default in daemon config), the daemon exports an evidence pack for each run with status FAIL.
- **Every run:** Set `evidence_pack_always: true` in daemon config to export an evidence pack for every run (e.g. for HIL/SIL or compliance). Increases disk use.

## Break-glass and overrides
- **Gate override:** To proceed despite FAIL when using HB as a release gate, run `hb analyze` or `hb run` with `--break-glass --override-reason "<reason>"`. Optionally set `--override-operator-id` and `--override-expires-in` (e.g. `24h`, `7d`). Requires approver/admin when `HB_RBAC=1`. See `docs/BREAK_GLASS_OVERRIDE.md`.

## Redaction on export
- **Evidence pack:** Use `hb export evidence-pack --case <id> --report-dir <dir> --redaction-policy <path> --redaction-profile <name>` to export with run_meta redacted (e.g. profile `pii` or `program_sensitive`). Define profiles in the policy YAML under `profiles:`.

## Custody and case timeline
- **List events for a case:** `hb custody timeline --case <run_id> --db runs.db` (case id is usually the run_id).
- **List recent events:** `hb custody list --db runs.db --limit 50`. Insert custody events when creating/exporting/transmitting evidence via `custody_event_insert()` in code or integrations.
- **Record export in custody:** Use `hb export evidence-pack ... --db runs.db [--operator-id <id>]` to record an "exported" custody event after a successful export.

## Tracing (optional)
- **OpenTelemetry:** If `opentelemetry-api` is installed, use `hb.tracing.span("name")` or `@trace_analyze` for ingest → decision → action spans. No-op if not installed. See `hb/tracing.py`. The analyze path is wrapped in a span automatically. Optional deps (KMS, Vault, OTel): `pip install -r hb/requirements-optional.txt`.

## Incident Recovery
- Restore `runs.db` from the latest backup.
- Re-run analyses as needed to regenerate reports.
- Verify integrity with manifests and signatures.
- Follow `docs/INCIDENT_RESPONSE.md` for field incidents.
