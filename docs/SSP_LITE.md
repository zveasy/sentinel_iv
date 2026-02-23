# System Security Plan (SSP) — Lite

**Purpose:** Minimum SSP-style document for security reviewers: system description, boundary, controls summary, and evidence pointers. Full SSP is program-specific.

**References:** `docs/COMPLIANCE_MATRIX.md`, `docs/THREAT_MODEL_CUSTOMER.md`, `docs/KEY_MANAGEMENT.md`.

---

## 1. System description

- **Name:** Harmony Bridge (HB), part of Sentinel-IV™ verification platform.
- **Purpose:** Drift detection and health assurance: compare telemetry/runs to baselines, produce reports and evidence, optionally recommend/request actions.
- **Boundary:** HB runs on a single node or cluster (daemon + optional UI); ingests from file, MQTT, Kafka, syslog; writes to local DB, report dir, and optional alert/action sinks. No cloud dependency; local-only UI by default.

---

## 2. Security boundary

- **In scope:** HB application, config, DB, report/evidence artifacts, action ledger, audit log.
- **Out of scope:** OS, network, third-party brokers (MQTT/Kafka), WaveOS or other control systems.

---

## 3. Control implementation summary

| Control family | Implementation | Evidence |
|----------------|----------------|----------|
| **Access (AC)** | RBAC (viewer, operator, approver, admin); per-program scope | `hb/rbac.py`; ADMIN_GUIDE |
| **Audit (AU)** | Hash-chained audit log; content and review | `hb/audit.py`; CUSTODY_AND_AUDIT |
| **Configuration (CM)** | Baseline request/approve; config hashes in evidence | POLICY_PROVENANCE |
| **Identification (IA)** | mTLS/JWT when API auth enabled; no passwords in HB | auth_middleware |
| **Incident (IR)** | Evidence pack, custody timeline, support bundle | RUNBOOK; INCIDENT_RESPONSE |
| **System/Comms (SC)** | KMS/Vault; encryption at rest; signed reports | KEY_MANAGEMENT; EVIDENCE_SIGNING |
| **Integrity (SI)** | SBOM; reproducible builds; audit chain | REPRODUCIBLE_BUILDS; COMPLIANCE_MATRIX |

Full mapping: **`docs/COMPLIANCE_MATRIX.md`** (NIST 800-53 / RMF).

---

## 4. Evidence and traceability

- **Requirement → implementation:** COMPLIANCE_MATRIX maps control ID to file/doc.
- **Implementation → evidence:** Audit log, artifact manifest, signed reports, custody_events; export via evidence-pack and support bundle.

---

## 5. Approval and maintenance

- **Approval:** Security reviewer or ATO authority signs off using this SSP-lite + COMPLIANCE_MATRIX + evidence.
- **Updates:** Revise when control implementation or boundary changes; version in doc header.
