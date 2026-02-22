# Distributor checklist (before you ship)

Use this list **before your first paid or customer-facing release**. These are **your** steps (legal, branding, process); not all are code.

---

## 1. Legal review

| Step | Action |
|------|--------|
| **EULA** | Have **counsel review** `release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt` before paid distribution. Update jurisdiction, liability caps, or other terms as needed for your company. |
| **Terms** | If you use a separate terms-of-use or order form, ensure it aligns with the EULA and is signed where required. |

---

## 2. Your support details

| Step | Action |
|------|--------|
| **Support email** | Replace **support@sentinel-iv.example.com** with your real support email in: `docs/SUPPORT.md`, and in any copy of SUPPORT.md included in the release kit. |
| **Support portal** | Replace **https://support.sentinel-iv.example.com** with your real portal URL in the same files. |
| **README** | Ensure the customer-facing README (e.g. `release/hb-hybrid-kit/README.md`) points to the correct support doc and contact. |

---

## 3. Your branding

| Step | Action |
|------|--------|
| **Company name** | If you distribute under a name other than Sentinel-IV, replace **Sentinel-IV** with your company name in: `release/hb-hybrid-kit/README.md`, `release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt`. |
| **Year** | Replace **2025** with the current year in the same files if needed. |
| **Placeholder check** | Run `python tools/check_release_placeholders.py`; it must pass (no `[COPYRIGHT HOLDER]`, `[YEAR]`, etc. left in checked files). |

---

## 4. License audit

| Step | Action |
|------|--------|
| **Generate report** | Follow **docs/THIRD_PARTY_LICENSES.md**: generate a license report (e.g. `pip-licenses` or `python tools/license_scan.py`) for the kit’s dependencies (`hb/requirements.txt`). |
| **Review** | Review `artifacts/licenses.json` (or equivalent) for **commercial use**: note any Non-Commercial, AGPL, or other restrictive licenses. |
| **Document** | Replace or remove incompatible deps, or **document exceptions** and get legal sign-off. Ship the license report (or instructions to generate it) with the kit. |

---

## 5. Optional

- **GPG signing:** Sign release zips per **docs/GPG_SIGNING.md** and document verification in release notes.
- **Changelog:** Update **CHANGELOG.md** for the release (version, date, list of changes).

---

**See also:** `docs/RELEASE_CHECKLIST.md`, `docs/COMMERCIAL_RELEASE_CHECKLIST.md`.
