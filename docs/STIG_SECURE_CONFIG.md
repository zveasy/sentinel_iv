# STIG-Aligned Secure Configuration Guide

**Purpose:** Hardening guidance aligned with DISA STIG concepts so HB can be deployed in DoD environments.

**References:** `docs/SECURE_INSTALL.md`, `docs/ADMIN_GUIDE.md`, `docs/KEY_MANAGEMENT.md`.

---

## 1. Least privilege

- **Process:** Run HB daemon and UI as a dedicated non-root user (e.g. `hb` or `harmony`). Use `deploy/install.sh` and systemd `User=hb`.
- **Files:** Restrict config and DB to owner read/write only (`chmod 600` for secrets, 640 for config).
- **RBAC:** Enable `HB_RBAC=1`; assign minimum role (viewer for read-only, operator for runs, approver for baseline approve).

---

## 2. Audit and logging

- **Audit log:** Enable and protect audit log; hash chain verification (`verify_audit_log`). Retain per program policy.
- **Log level:** Avoid verbose logging in production; use structured logs and correlation_id for traceability.
- **No sensitive data in logs:** Redact secrets; use `HB_REJECT_PLAINTEXT_SECRETS=1` so plaintext secrets are rejected in config.

---

## 3. Cryptography and keys

- **Encryption at rest:** Use SQLCipher for DB (`hb db encrypt`); use `--encrypt-key` for evidence packs. Prefer KMS/Vault over file-based keys.
- **Signing:** Use Ed25519 or org PKI for report signing; protect signing key; rotate per KEY_MANAGEMENT.md.
- **TLS:** Use TLS for API/UI when exposed; disable TLS 1.0/1.1.

---

## 4. Network and binding

- **UI and feedback:** Bind to localhost only (127.0.0.1); do not bind to 0.0.0.0 in classified or untrusted networks.
- **Inbound:** Only open ports required (e.g. health/metrics if used); restrict by firewall.

---

## 5. Configuration management

- **No default secrets:** No hardcoded passwords or API keys; use env or KMS.
- **Config validation:** Run with `HB_REJECT_PLAINTEXT_SECRETS=1`; validate metric_registry and baseline_policy at startup.
- **Version control:** Track config in version control; use config hashes in evidence for reproducibility.

---

## 6. Patching and supply chain

- **SBOM:** Generate and verify SBOM (`tools/generate_sbom.py`, `tools/verify_sbom.py`).
- **Vulnerability scan:** Run pip-audit; track in POA&M (see `docs/POAM_TEMPLATE.md`).
- **Reproducible builds:** Follow `docs/REPRODUCIBLE_BUILDS.md` for release builds.

---

## 7. Checklist (summary)

- [ ] Non-root user for daemon/UI
- [ ] RBAC enabled; least privilege roles
- [ ] Audit log enabled and hash chain verified
- [ ] No plaintext secrets in config
- [ ] DB and evidence encryption where required
- [ ] UI/API bound to localhost or behind TLS + auth
- [ ] SBOM and vulnerability workflow in place
