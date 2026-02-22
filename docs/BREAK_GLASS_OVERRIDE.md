# Break-Glass Override

Emergency override of a gate or baseline decision with tight logging and optional expiry.

## Concept

- **Break-glass:** An operator temporarily overrides a failing gate or baseline rule (e.g. “proceed despite FAIL”) for a defined reason and duration.
- **Requirements:** Override must be logged (who, when, reason, scope); should have an expiry so it does not stay in effect indefinitely.

## Implementation options

1. **CLI flag + audit:** Add an optional `--break-glass` (or `--override`) to commands that enforce gates (e.g. `analyze` or release gate). When set:
   - Require `--override-reason` (and optionally `--override-operator-id`).
   - Log to audit (e.g. `custody_events` or audit_log.jsonl) with `event_type: break_glass_override`, `operator_id`, `reason`, `expires_at` (e.g. now + 24h).
   - Proceed with the operation (e.g. exit 0 even if status is FAIL when used as gate).
2. **Expiry:** A separate job or next run can check `expires_at` and warn or block if an override has expired and the condition still fails.
3. **RBAC:** Restrict who can use break-glass (e.g. only `admin` or `approver` when `HB_RBAC=1`).

## Current state

- **CLI:** `hb analyze` and `hb run` support `--break-glass` with required `--override-reason`, optional `--override-operator-id` and `--override-expires-in` (e.g. `24h`, `7d`). When status is FAIL and `HB_GATE_FAIL_EXIT=1`, using `--break-glass` logs the override to the report’s audit log and exits 0 instead of 2.
- **Audit:** A `break_glass_override` entry is appended to `report_dir/audit_log.jsonl` with `reason`, `operator_id`, and `expires_at`.
- **RBAC:** When `HB_RBAC=1`, the `override` operation requires approver or admin role.
