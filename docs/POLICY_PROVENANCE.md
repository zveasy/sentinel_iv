# Policy Provenance

Track who changed policy, when, and what version is in effect for audit and rollback.

## Baseline policy

- **Stored in:** `baseline_policy.yaml` (or path in config). No automatic versioning in-repo; use Git or your deployment pipeline to track changes.
- **Provenance:** When loading policy, the code records config hashes in the evidence manifest (`write_config_snapshot_hashes(baseline_policy_path=...)`) so each run knows which policy file (by hash) was used. For “who/what updated,” rely on:
  - **Git history** for the repo that holds `baseline_policy.yaml`: `git log -p -- baseline_policy.yaml`.
  - **Deployment audit:** If policy is deployed from a CI/CD pipeline, use pipeline logs and approvers.
- **Approval workflow:** Baseline **approvals** are stored in the DB (`baseline_approvals` table) with `approved_by`, `reason`, `approved_at`, and `request_id`. Use `hb baseline approvals` to list. Requests are in `baseline_requests` with `requested_by` and `reason`.

## Metric registry

- Same pattern: registry path is hashed and stored in run/evidence. Use Git or deployment history for who changed `metric_registry.yaml`.

## Extending provenance

- **Optional:** On load, append an audit event (e.g. to `custody_events` or an audit log) with `event_type: policy_loaded`, `payload: { path, sha256, loaded_at }`. That gives a queryable record of which policy was used when, without modifying the policy file itself.
