# Secure Install Checklist (DoD Lab)

Pre-install:
- Verify repo checksum or signed artifact.
- Verify `SBOM.md` matches expected dependencies.
- Ensure offline wheelhouse is trusted.

Install:
- Use `docs/OFFLINE_INSTALL.md` to install from local wheelhouse.
- Store keys in a restricted directory (`keys/`).

Post-install:
- Run `bin/hb run` on a known-good sample.
- Validate `artifact_manifest.json` and `audit_log.jsonl` are created.
- Optionally sign reports with `--sign-key`.
- If encryption is required, use `--encrypt-key` for report artifacts and SQLCipher for `runs.db`.
- Run `python tools/license_scan.py --out artifacts/licenses.json --format json`.
