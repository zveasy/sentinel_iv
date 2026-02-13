# Harmony Bridge — Hybrid Kit

**Copyright (c) [YEAR] [COPYRIGHT HOLDER].** See [License](#license) below.

Harmony Bridge compares run metrics to a baseline, detects drift, and produces reports so you can catch regressions and explain changes. This kit includes:

- **CLI** for automation and CI (compare, plan run, support commands)
- **Local Web UI** for quick evaluation and inspection
- Shared compare pipeline, run registry, and HTML/JSON/PDF reports

All processing runs on your machine. No data is sent off-box unless you explicitly configure an optional integration.

---

## System requirements

- **Python:** 3.10 or 3.11 (3.12 supported where dependencies allow)
- **OS:** Linux, macOS, or Windows (WSL recommended on Windows for CLI)
- **Disk:** ~500 MB for kit + venv; more for output and run registry
- **Network:** Not required after install (offline use supported; see [Offline install](#offline-install))

---

## Installation

### Standard install

1. Extract the kit and open a shell in the kit directory.
2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r hb/requirements.txt
   ```

3. Verify:

   ```bash
   ./bin/hb --help
   ```

### Offline install

For air-gapped or offline environments, use an offline wheelhouse. See **docs/OFFLINE_INSTALL.md** in the full project or ask your distributor for the offline install guide.

### Secure install (labs / high-assurance)

Verify the release integrity (checksums or signatures) as described in **docs/INTEGRITY_VERIFICATION.md**, then follow **docs/SECURE_INSTALL.md** for checksum verification, trusted wheelhouse, and post-install checks.

### Docker

```bash
docker build -t hb-hybrid-kit .
docker run --rm -p 8765:8765 hb-hybrid-kit
```

Then open http://127.0.0.1:8765 for the local UI.

---

## Quick start

- **Local UI:** Run `./bin/hb ui` and open http://127.0.0.1:8765. The server binds to localhost only; no data is uploaded.
- **CLI compare:** See **QUICKSTART.md** in this directory for a minimal compare example and Docker usage.

---

## License

- **Commercial use:** See **LICENSE_COMMERCIAL.txt**. Use this license when you have a commercial agreement or order form with [COPYRIGHT HOLDER].
- **Evaluation only:** See **LICENSE_EVAL.txt** for internal evaluation. No production use or redistribution under the eval license without a signed agreement.

Replace `[COPYRIGHT HOLDER]` and `[YEAR]` with the actual vendor name and year before distribution.

---

## Support

- **How to get help:** See **docs/SUPPORT.md** for contact details and how to open a support request.
- **Before contacting support:** Run `./bin/hb support health`. When opening a ticket, include a **support bundle**:  
  `./bin/hb support bundle --out support_bundle.zip`  
  Attach the zip to your request (see docs/SUPPORT.md for what’s included).

---

## Security and compliance

- **Security posture and threat model:** **docs/THREAT_MODEL_CUSTOMER.md** — local-only operation, data flow, and hardening.
- **Integrity verification:** **docs/INTEGRITY_VERIFICATION.md** — how to verify checksums (and signatures if provided).
- **SBOM:** A Software Bill of Materials or license report is provided with the release for dependency and license review.

---

## Changelog and release notes

See **CHANGELOG.md** in the project repository or the release notes provided with your download for version history and fixes.
