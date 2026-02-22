# Release Checklist

Use this list before cutting a commercial or customer-facing release. Ensures placeholders are replaced, legal/support are set, and artifacts are ready.

**Distributor steps (legal, support, branding, license audit):** See **docs/DISTRIBUTOR_CHECKLIST.md**.

---

## Pre-release (must pass)

| Step | Command / action | Notes |
|------|------------------|--------|
| **1. Placeholders** | `python tools/check_release_placeholders.py` | Must exit 0. Defaults (Sentinel-IV, 2025, support@sentinel-iv.example.com) are set; replace with your company details for your distribution. |
| **2. EULA** | Legal review of `release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt` | Use for paid distribution; get legal sign-off. |
| **3. Support** | Set real contact in `docs/SUPPORT.md` | Replace example email/portal with your support contact. |
| **4. Changelog** | Update `CHANGELOG.md` | Add version and date; list changes and fixes for this release. |
| **5. SBOM** | `python tools/generate_sbom.py --out SBOM.md --from-installed` | Run from a venv with deps installed. Commit or ship `SBOM.md` with the kit. |
| **6. Vulnerability scan** | `pip install pip-audit && pip-audit -r hb/requirements.txt -r hb/requirements-dev.txt` | Fix or document any reported vulnerabilities before release. |
| **7. Build kit** | `python tools/build_kit.py --checksums` | Produces versioned zip and checksums. |
| **8. Integrity** | Verify `docs/INTEGRITY_VERIFICATION.md` is in kit | Customers use this to verify the download. |

---

## Optional

| Step | Action |
|------|--------|
| **Third-party licenses** | See `docs/THIRD_PARTY_LICENSES.md`; run license scan and audit for commercial use. |
| **GPG signing** | When you tag releases, optionally sign zips per `docs/GPG_SIGNING.md`; document verification in release notes. |

---

## CI

The following run on every push/PR (see `.github/workflows/ci.yml`):

- `python tools/check_release_placeholders.py` — fails if placeholders remain.
- `pip-audit -r hb/requirements.txt -r hb/requirements-dev.txt` — fails if known vulnerabilities are reported.

On push of a version tag (e.g. `v0.3.0`), `.github/workflows/release.yml` runs: generates SBOM, builds kit with checksums, uploads artifacts. Before tagging, ensure CI is green and complete the pre-release steps above.

---

**See also:** `docs/COMMERCIAL_RELEASE_CHECKLIST.md`, `docs/PRODUCTION_READINESS_REVIEW.md`.
