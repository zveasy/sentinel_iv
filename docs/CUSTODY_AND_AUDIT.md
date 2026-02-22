# Chain-of-Custody and Operator Attribution

## Custody events

The `custody_events` table records who touched a case and when:

- **event_id** — Unique id (e.g. UUID).
- **case_id** — Run id or case identifier.
- **event_type** — `created` | `accessed` | `exported` | `transmitted`.
- **ts_utc** — Timestamp.
- **operator_id** — Identity of the operator (from RBAC or CLI).
- **reason** — Optional reason code or free text.
- **payload** — Optional JSON (e.g. export path, recipient).

Use `custody_event_insert(conn, event_id, case_id, event_type, operator_id=..., reason=...)` when creating/exporting/transmitting evidence. Use `custody_events_list(conn, case_id=...)` to build a timeline for a case.

## Operator identity and reason codes

- **Baseline approve:** `hb baseline approve` already requires `--approved-by` and `--reason`; these are stored in `baseline_approvals`.
- **Override:** For any override (e.g. skip quality gate, force set), use `--reason` and store in audit log; operator can be passed via `--operator-id` or from RBAC context when implemented.
- **Export:** When exporting evidence pack or reports, log a custody event with `event_type=exported`, `operator_id`, and `reason`.

## Redaction profiles (export controls)

- Redaction is configured via `redaction_policy.yaml` and applied with `--redaction-policy` on analyze/run.
- **Named profiles:** In the policy YAML use `profiles: { pii: { redact: {...} }, program_sensitive: { redact: {...} } }`. Then run `hb export evidence-pack --case <id> --report-dir <dir> --redaction-policy <path> --redaction-profile program_sensitive` to export a pack with run_meta redacted according to that profile.
