# Third-Party Licenses

## Audit for commercial use

Before commercial distribution:

1. **Generate license report** (from repo root, with venv activated):
   ```bash
   pip install pip-licenses  # or use tools/license_scan.py if present
   pip-licenses --format=json --output-file=artifacts/licenses.json
   ```
   Or: `python tools/license_scan.py --out artifacts/licenses.json --format json`

2. **Review** `artifacts/licenses.json` (or the report shipped with the kit):
   - Identify any **Non-Commercial**, **AGPL**, or **copyleft** licenses that may restrict commercial use or distribution.
   - Replace or remove dependencies with incompatible licenses, or document the exception and legal sign-off.

3. **Ship with release:** Include the license report (or a link to how to generate it) in the release kit so customers can review third-party components.

## Kit dependencies

Core runtime dependencies are listed in `hb/requirements.txt`. Dev and optional dependencies may appear in `hb/requirements-dev.txt` and other requirement files. The SBOM (`python tools/generate_sbom.py --out SBOM.md --from-installed`) lists package names and versions for the installed environment.

## Notes

- **Placeholder:** If you distribute under a different vendor name, ensure your legal team has approved use of all third-party components for your commercial offering.
- **Updates:** Re-run the license scan when adding or upgrading dependencies.
