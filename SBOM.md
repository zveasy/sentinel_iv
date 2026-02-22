# Software Bill of Materials (SBOM)

Generate the full SBOM (package names and versions) by running:

```bash
# From repo root, with deps installed (e.g. in a venv):
pip install -r hb/requirements.txt -r hb/requirements-dev.txt
python tools/generate_sbom.py --out SBOM.md --from-installed
```

Without `--from-installed`, versions are taken from pinned requirements only. Include the generated `SBOM.md` (or equivalent) with each release for dependency and license review.

- **Dependencies:** See `hb/requirements.txt` and `hb/requirements-dev.txt`.
- **Optional tools:** wkhtmltopdf (for PDF reports).
