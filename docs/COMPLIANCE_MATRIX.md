# Compliance Matrix — NIST 800-53 and RMF Alignment

**Purpose:** Explicit mapping of Harmony Bridge to security and audit controls expected in DoD and federal environments (NIST 800-53, Risk Management Framework). Use this for certification and authority to operate (ATO) discussions.

**References:** NIST SP 800-53 Rev. 5; `docs/SECURITY_POSTURE.md`, `docs/CUSTODY_AND_AUDIT.md`, `docs/KEY_MANAGEMENT.md`, `docs/EVIDENCE_SIGNING.md`.

---

## How to read this matrix

- **Control:** NIST 800-53 control family and identifier.
- **Implementation:** Where and how HB implements or supports the control.
- **Evidence:** Artifacts or procedures to demonstrate compliance.

---

## Access Control (AC)

| Control | Title | Implementation | Evidence |
|---------|--------|-----------------|----------|
| **AC-2** | Account Management | RBAC: roles (viewer, operator, approver, admin); per-program scope. | `hb/rbac.py`; `HB_RBAC=1`; `docs/ADMIN_GUIDE.md` |
| **AC-3** | Access Enforcement | Permission checks on baseline set/approve, export evidence-pack, db encrypt/decrypt when RBAC enabled. | `hb/rbac.py` `has_permission`, `require_role` |
| **AC-6** | Least Privilege | Roles limit who can approve baselines, export evidence, override. | Admin guide; role matrix in runbook |
| **AC-7** | Unsuccessful Logon / Lockout | Not implemented in HB (handled by OS/IdP). | Document as OS/network responsibility |
| **AC-17** | Remote Access | HB does not accept remote access by default; UI binds localhost. | `bin/hb ui`; README local-only |

---

## Audit and Accountability (AU)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **AU-2** | Auditable Events | Baseline set/request/approve, analyze, action execute, evidence export, break-glass. | Events in audit trail; configurable |
| **AU-3** | Content of Audit Records | Audit log with timestamp, actor, action, outcome; hash-chained. | `hb/audit.py`; `verify_audit_log`; `docs/CUSTODY_AND_AUDIT.md` |
| **AU-3(1)** | Additional Audit Information | Correlation IDs, run_id, decision_id in reports and logs. | Report payload; structured logs |
| **AU-6** | Audit Review, Analysis, and Reporting | Custody timeline, audit log review; export for SIEM. | `hb custody timeline`; `hb custody list`; RUNBOOK |
| **AU-7** | Audit Reduction and Report Generation | Audit log and report dir; support bundle for export. | `hb support bundle`; retention/rotate tools |
| **AU-9** | Protection of Audit Information | Audit log integrity via hash chain; optional signing. | `hb/audit.py` chain; EVIDENCE_SIGNING |

---

## Assessment, Authorization (AT)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **AT-1** | Policy and Procedures | Security and operational docs (RUNBOOK, ADMIN_GUIDE, SECURE_INSTALL). | `docs/` |
| **AT-2** | Literacy Training | Not HB-provided; customer responsibility. | Document as customer |

---

## Configuration Management (CM)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **CM-3** | Configuration Change Control | Baseline request/approve workflow; policy versioning; config hashes in evidence. | `hb baseline request/approve`; POLICY_PROVENANCE |
| **CM-5** | Access Restrictions for Change | RBAC: only approver/admin can approve baselines; break-glass logged. | `hb/rbac.py` |
| **CM-6** | Configuration Settings | Thresholds, metric registry, baseline policy under version control; hashes in manifest. | Config files; artifact manifest |

---

## Identification and Authentication (IA)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **IA-2** | Identification and Authentication | When RBAC=1, role/identity from env or integration; API: mTLS + optional JWT. | `hb/auth_middleware.py`; ADMIN_GUIDE |
| **IA-5** | Authenticator Management | No password storage in HB; KMS/Vault for keys. | KEY_MANAGEMENT.md |

---

## Incident Response (IR)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **IR-4** | Incident Handling | Evidence pack export, custody timeline, support bundle for investigation. | `hb export evidence-pack`; RUNBOOK; `docs/INCIDENT_RESPONSE.md` |
| **IR-6** | Incident Reporting | Audit log and alerts; integration with webhook/sink for notification. | Alerting sinks; RUNBOOK |

---

## Maintenance (MA)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **MA-3** | Maintenance Tools | Support bundle and health check; no unapproved tools required. | `hb support health`, `hb support bundle` |

---

## Media Protection (MP)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **MP-6** | Media Sanitization | Customer responsibility for disk/drive sanitization. | Document as customer |

---

## Physical and Environmental (PE)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **PE-*** | Physical Security | Out of scope for HB software. | Customer / facility |

---

## Risk Assessment (RA)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **RA-3** | Risk Assessment | Threat model (THREAT_MODEL_CUSTOMER.md); risk in security posture. | `docs/THREAT_MODEL_CUSTOMER.md`; SECURITY_POSTURE |

---

## System and Communications Protection (SC)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **SC-8** | Transmission Confidentiality and Integrity | TLS for API/UI when deployed; optional signing of reports. | Deploy with TLS; EVIDENCE_SIGNING |
| **SC-12** | Cryptographic Key Establishment and Management | KMS (AWS/Vault) integration; key rotation; no plaintext secrets in config. | `hb/keys.py`; KEY_MANAGEMENT.md; config_validation |
| **SC-13** | Cryptographic Protection | Signed reports (Ed25519/org PKI); encrypted DB (SQLCipher); encrypted evidence packs. | EVIDENCE_SIGNING; `hb db encrypt`; `--encrypt-key` |
| **SC-28** | Protection of Information at Rest | Encrypted DB; encrypted evidence; optional full-disk encryption by OS. | SQLCipher; KEY_MANAGEMENT |

---

## System and Information Integrity (SI)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **SI-3** | Malicious Code Protection | No execution of user-supplied code; SBOM and dependency scan. | SBOM; pip-audit; SECURE_CODING |
| **SI-7** | Software, Firmware, and Information Integrity | Hash-chained audit log; signed config snapshots; reproducible builds. | REPRODUCIBLE_BUILDS; audit chain; evidence manifest |
| **SI-12** | Information Handling and Retention | Redaction profiles; retention policy; custody and disposal. | Redaction policy; retention_prune; CUSTODY_AND_AUDIT |

---

## Program Management (PM)

| Control | Title | Implementation | Evidence |
|---------|--------|----------------|----------|
| **PM-9** | Risk Management Strategy | Threat model and security posture; risk in program docs. | THREAT_MODEL; SECURITY_POSTURE |

---

## RMF (Risk Management Framework) alignment

- **Categorize:** Use NIST 800-60 for system categorization; HB as component in larger system.
- **Select:** Apply 800-53 controls per categorization; this matrix is the HB **implementation** mapping.
- **Implement:** Controls above implemented in code and docs.
- **Assess:** Use this matrix + V&V package + evidence (audit log, signed artifacts) for assessor review.
- **Authorize:** Authorizing official uses assessment results; HB provides evidence and compliance narrative.
- **Monitor:** Ongoing audit review, key rotation, patch and SBOM updates per RUNBOOK and release process.

---

## Summary table (quick reference)

| Control | Implementation |
|---------|----------------|
| **AC-2** | RBAC in `hb/rbac.py` |
| **AU-3** | Audit log + hash chain in `hb/audit.py` |
| **SC-12** | Encryption at rest; KMS/Vault in `hb/keys.py`; KEY_MANAGEMENT.md |
| **SC-13** | Signed reports; encrypted DB and evidence |
| **SI-7** | Integrity: chain, signed snapshots, reproducible builds |

This matrix should be updated when controls are added or implementation changes. Maintain in version control with the rest of `docs/`.

**Related artifacts for certification:**

- **System Security Plan (lite):** `docs/SSP_LITE.md` — system description, boundary, controls summary.
- **Control implementation statements:** This matrix is the implementation mapping; expand rows with specific file:line or procedure references as needed for assessor.
- **POA&M:** `docs/POAM_TEMPLATE.md` — vulnerability management workflow and POA&M template.
- **Secure configuration:** `docs/STIG_SECURE_CONFIG.md` — STIG-aligned hardening guide.
- **Build provenance:** `docs/SLSA_BUILD_PROVENANCE.md` — SBOM and signed build posture.
