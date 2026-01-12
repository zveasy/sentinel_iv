# Production Readiness Assessment

Score: 35 / 100

Rationale:
- Solid MVP flow (ingest -> reduce -> compare -> report) exists for CSV/logs.
- Missing dependency management and deployment packaging.
- No persistent storage, run registry, or audit trail.
- Limited parsing resilience and validation for real lab data.
- No automated tests or regression suite.

Checklist

Data ingestion and validation:
- Support multiple real-world formats (Excel sheets, CSV variants, log schemas).
- Strong schema validation with clear error messages.
- Unit normalization and consistent metric naming.

Metrics and configuration:
- Versioned metric definitions and thresholds per program.
- Percent/absolute drift rules and rolling baselines.
- Config validation with defaults.

Storage and traceability:
- Run registry (SQLite/Postgres) with metadata.
- Immutable artifacts, hashes, and audit logs.
- Baseline lineage and provenance tracking.

Reporting and visualization:
- Branded HTML/PDF with summary tables.
- Diff visualizations and trend charts.
- Exportable artifacts for QA/audits.

Security and compliance:
- Access control, encryption at rest, secure logging.
- Redaction options for sensitive data.
- SBOM, license scan, and secure coding standards.

Reliability and performance:
- Deterministic output, idempotent runs.
- Graceful failures with clear exit codes.
- Large-file and long-run performance profiling.

Testing:
- Unit tests for parsers and metrics.
- Golden-file tests for reports.
- Regression suite with real lab samples.

Packaging and operations:
- Installable CLI (pipx/binary) with pinned deps.
- Offline install plan and versioned releases.
- Monitoring hooks and support diagnostics.
