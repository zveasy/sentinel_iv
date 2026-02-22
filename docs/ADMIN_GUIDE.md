# Admin Guide: Keys, RBAC, Retention, HA

## Keys and signing

- **Signing key:** Use `--sign-key <path>` for analyze/run; key file must be readable only by the process. Prefer Ed25519 (see `docs/EVIDENCE_SIGNING.md`).
- **Key rotation:** When rotating, use a new key and record `signing_key_version` in the manifest (e.g. `v2`). Keep old public keys to verify historical manifests. See `docs/KEY_MANAGEMENT.md` (stub).
- **Encryption key:** `--encrypt-key` for report encryption; same handling as signing (file or env, no plaintext in config).

## RBAC (roles)

- **Roles:** `viewer` | `operator` | `approver` | `admin`. Set `HB_ROLE` for CLI; API would use token/header.
- **Sensitive ops:** Baseline set/approve, override, export evidence-pack, db encrypt/decrypt require approver or admin.
- **Per-program:** When enabled, operator/approver scope is limited to allowed programs (config or DB). See `hb/rbac.py`.

## API auth (mTLS / JWT)

- **Stub:** `hb/auth_middleware.py` provides `AuthConfig`, `check_request_auth()`, and `wrap_handler_with_auth()` for config-driven auth. Set `auth.mtls_required: true` and `auth.mtls_dn_header` (e.g. `X-Client-DN` set by reverse proxy) to require client cert; use `HB_ALLOW_NO_AUTH=1` only in dev. Full mTLS is typically terminated at the load balancer; JWT/OPA validation can be extended in the same module.

## Retention

- **Runs:** Use `tools/retention_prune.py --policy retention_policy.yaml --db runs.db` to prune old runs.
- **Reports:** Rotate or archive with `tools/audit_rotate.py`; cap size with `max_report_dir_mb` in daemon config.

## HA and failover

- **Checkpoints:** Daemon writes `daemon_checkpoint.json` each cycle; on restart it resumes from last cycle. For persistent history, see roadmap §5.1.4 (checkpoint history).
- **Active/standby:** Run one daemon as primary; standby can take over by using the same DB and report dir (single-writer to DB). Document your failover procedure (who promotes standby, how to sync checkpoints if needed).
