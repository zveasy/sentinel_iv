# Reproducible Builds

Build the same artifacts from the same source and dependencies for audit and supply-chain verification.

## Lockfile

- **Python:** Use pinned requirements. The repo uses `hb/requirements.txt` and `hb/requirements-dev.txt` with version pins where possible. For full reproducibility, generate a lockfile (e.g. `pip compile` from pip-tools) and commit it; install with `pip install -r requirements.lock` in CI and release builds.
- **Example lockfile generation:**
  ```bash
  pip install pip-tools
  pip-compile hb/requirements.txt -o hb/requirements.lock
  pip-compile hb/requirements-dev.txt -o hb/requirements-dev.lock
  ```

## Build script

- Use a single entrypoint for release builds (e.g. `tools/build_kit.py`) so the same steps run in CI and locally. Include in the script: install from lockfile (or pinned requirements), run tests, generate SBOM, build package/container.
- Avoid embedding build timestamps or host-specific paths in artifacts when possible so that two builds from the same commit produce identical output (or document where non-determinism remains).

## Environment

- Set `PYTHONHASHSEED=0` (or a fixed value) when running tests and build so hash-based ordering is deterministic.
- Use the same Python minor version in CI and release (e.g. 3.11 or 3.12) as in the roadmap.

## Verification

- CI can compare two builds from the same ref (e.g. checksums of wheels or SBOM) to detect unintended variation. SBOM generation and verification are already in the release workflow (`tools/generate_sbom.py`, `tools/verify_sbom.py`).
