# Harmony Bridge — Security Posture & Threat Model (Customer)

This document describes the security posture of Harmony Bridge for commercial and production deployments. **Review this before deployment** if you have security or compliance requirements.

## Deployment Model: Local-Only

- **All processing is on your hardware.** The CLI and local web UI run on the machine where you install the kit. No metrics, reports, or artifacts are sent to external servers.
- **Web UI binding:** The UI server binds to `127.0.0.1` (localhost) only. It is not reachable from the network unless you explicitly change configuration.
- **No telemetry.** The software does not phone home, collect usage analytics, or transmit data off your system by default.

## Data Flow (No Off-Box Transmission)

| Data | Where it lives | Sent off-box? |
|------|----------------|----------------|
| Run artifacts (metrics, logs) | Your chosen output directory | No |
| Baseline and current run data | Local disk | No |
| Reports (HTML/JSON/PDF) | Local output directory | No |
| Run registry (SQLite) | Local `runs.db` | No |
| Feedback (optional) | Only if you explicitly enable and configure it | Configurable |

If you enable any optional feedback or integration feature, that will be documented in the configuration; the default install does not send data off the host.

## Threat Model Summary

- **Design goal:** Support lab and production use on air-gapped or locked-down networks without requiring outbound connectivity.
- **Trust boundary:** Your trust boundary is the machine(s) where Harmony Bridge runs. Protect access to that host (OS and file permissions).
- **Secrets:** The kit does not embed API keys or secrets. Any signing or encryption keys you use (e.g. `--sign-key`, `--encrypt-key`) are provided by you and stored under your control.
- **Supply chain:** Verify release integrity using the checksums and (if provided) signatures as described in `INTEGRITY_VERIFICATION.md`. Use the provided SBOM to review third-party components.

## Recommended Hardening

- **Install:** Follow `SECURE_INSTALL.md` for checksum verification, offline wheelhouse verification, and post-install checks.
- **Access control:** Restrict filesystem and database permissions to the service/user account that runs Harmony Bridge.
- **Network:** Keep the HB host on a management or lab segment; do not expose the UI port to untrusted networks.
- **Keys:** Store signing/encryption keys in a restricted directory (e.g. `keys/`) with minimal read access.
- **Updates:** Apply updates from official, integrity-verified releases only.

## Compliance and Audits

- **SBOM:** A Software Bill of Materials (or instructions to generate one) is provided with the release for dependency review.
- **Licenses:** Run `python tools/license_scan.py` (or use the provided license report) to review third-party licenses for compliance.
- **Sensitive data:** Use redaction options before generating reports if they will be shared or archived (see user guide).

For operator runbooks, incident response, and rollback procedures, see `RUNBOOK.md`, `INCIDENT_RESPONSE.md`, and `ROLLBACK_PROCEDURE.md` in this documentation set.
