# Build Provenance (SLSA-Inspired Posture)

**Purpose:** Document SBOM and signed build provenance so deployers can verify what was built and from what.

**References:** `tools/generate_sbom.py`, `tools/verify_sbom.py`, `docs/REPRODUCIBLE_BUILDS.md`, `docs/CONTAINER_SIGNING.md`.

---

## 1. SBOM

- **Generate:** `python tools/generate_sbom.py --out SBOM.md` (or `--from-installed`).
- **Verify:** `python tools/verify_sbom.py SBOM.md` in CI and before release.
- **Artifact:** Include SBOM in release package; reference in release notes.

---

## 2. Reproducible builds

- **Lockfile:** Use locked requirements (e.g. `requirements.txt` with pinned versions) for release.
- **Build script:** Document build steps in `docs/REPRODUCIBLE_BUILDS.md`; use consistent PYTHONHASHSEED and env.
- **Checksums:** `python tools/build_kit.py --checksums` produces checksums for release zip; document in INTEGRITY_VERIFICATION.

---

## 3. Signed build provenance (SLSA-ish)

- **Level 0–1:** SBOM + checksums + reproducible build doc.
- **Level 2+:** Sign release zip (GPG/cosign) and attest build env (CI runner, commit, inputs). Document in release process and `docs/CONTAINER_SIGNING.md` for containers.
- **Verification:** Customer verifies signature and checksums before install; see `docs/INTEGRITY_VERIFICATION.md`.

---

## 4. Evidence for reviewer

- Security reviewer can trace: **requirement → implementation → evidence** via COMPLIANCE_MATRIX, SSP-lite, and this doc (SBOM, checksums, signing).
