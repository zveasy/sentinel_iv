# License Scan

Run a local license scan of installed Python dependencies:

```
python tools/license_scan.py --out artifacts/licenses.json --format json
```

CSV output:

```
python tools/license_scan.py --out artifacts/licenses.csv --format csv
```

Notes:
- The scan reads package metadata from the current environment.
- Store outputs with your release artifacts alongside `SBOM.md`.
