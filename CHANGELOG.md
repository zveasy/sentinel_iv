# Changelog

All notable changes to Harmony Bridge are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

**Before each release:** Update the version and date below; add entries under Added/Changed/Fixed/Security as needed. See `docs/RELEASE_CHECKLIST.md`.

---

## [Unreleased]

- Commercial release packaging: EULA template, threat model doc, integrity verification, support doc, customer README.

## [0.3.0] — (see release notes)

### Added

- CLI and local web UI for drift analysis and reporting.
- Compare pipeline: baseline vs current run, drift detection, threshold and invariant checks.
- Plan runner: `hb plan run` with scenario modes, requirement traceability, trace matrix export.
- Reports: HTML/JSON/PDF with "why flagged" narratives, diff visualizations, trend charts.
- Run registry (SQLite), artifact hashing, optional signing and encryption.
- Support commands: `hb support health`, `hb support bundle`.
- Offline install path and secure install checklist.
- Docker image for local UI.

### Changed

- (Version-specific changes listed in release notes.)

### Security

- Local-only UI binding; no telemetry; redaction options for reports.
- SBOM and license scan tooling; secure install and threat model documentation.

---

For upgrade and install instructions, see the README in the release kit and `docs/OFFLINE_INSTALL.md`.
