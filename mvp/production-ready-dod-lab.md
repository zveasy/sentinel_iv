# Production Ready: DoD Lab Deployment (Offline)

Target: Offline lab deployment with auditability, secure install, and long-term sustainment.

Scope:
- Offline-capable CLI + local UI/report access.
- Immutable artifacts and audit trails.
- Secure installation and dependency pinning.

Checklist to reach 100:
- Data ingestion: robust parsers for real lab outputs and unit normalization.
- Validation: strict schema validation with signed configs.
- Storage: local database (SQLite/Postgres), immutable artifact store, hashes.
- Auditability: run provenance, config versions, chain-of-custody.
- Security: encryption at rest, access control, secure logging, redaction.
- Packaging: offline install bundle, signed releases, SBOM.
- Reliability: idempotent runs, deterministic output, rollback plan.
- Testing: regression suite with real lab datasets, load tests.
- Documentation: deployment guide, operator runbook, upgrade SOP.

Deliverables:
- Offline install bundle + signed artifacts.
- Audit trail and provenance report outputs.
- Lab deployment runbook and secure config management.

Current status:
- Offline install instructions in `docs/OFFLINE_INSTALL.md`.
- Secure install checklist in `docs/SECURE_INSTALL.md`.
- Runbook in `docs/RUNBOOK.md`.
- Artifact manifests, audit logs, and signatures available.
- SQLCipher tooling for encrypted registry.
