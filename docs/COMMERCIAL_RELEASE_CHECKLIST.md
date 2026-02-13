# Commercial Release Checklist

What needs to be done before giving Harmony Bridge out **commercially** (licensed software to customers). This complements the internal production-readiness rubric and focuses on **legal, packaging, support, and trust** for a commercial offering.

---

## 1. Legal & Licensing (must-have)

| Item | Status | Notes |
|------|--------|--------|
| **Commercial license / EULA** | Not done | Replace or supplement `release/hb-hybrid-kit/LICENSE_EVAL.txt`. Eval license currently says: *"No redistribution, resale, or production use is permitted without a signed agreement."* You need a commercial license that explicitly permits production use, redistribution (if applicable), and support terms. |
| **Terms of use / EULA** | Not done | Define permitted use, restrictions, warranty disclaimer, limitation of liability, indemnity (if any), and governing law. Get legal review. |
| **Third-party licenses** | Partial | `tools/license_scan.py` + `artifacts/licenses.json` exist. Ensure commercial use of all dependencies is allowed (e.g. note any "Non-Commercial" deps in `licenses.json` and replace or document). |
| **Copyright and notices** | Partial | Add clear copyright and license notices in the kit (e.g. README, installer) so customers know who they’re licensing from. |

**Deliverables:** Commercial EULA or license file in the release kit; optional separate “Terms of Use” for download/portal; license compliance note for dependencies.

---

## 2. Packaging & Distribution (must-have)

| Item | Status | Notes |
|------|--------|--------|
| **Signed / verified releases** | Partial | Production-readiness mentions “Signed kit release + integrity verification docs.” Ensure every commercial build is signed and that `docs/` (or release notes) explain how to verify integrity (checksums, signatures). |
| **Versioned releases** | Done | `VERSION` and versioned kit name (e.g. `hb-hybrid-kit-v0.3.0`) are in place. |
| **Customer-facing README** | Partial | `release/hb-hybrid-kit/README.md` is short. Add: system requirements, install steps (incl. optional offline), link to license/EULA, where to get support, and link to release notes/changelog. |
| **Changelog / release notes** | Not done | Maintain a CHANGELOG or release notes per version so customers know what changed and what’s fixed. |
| **Install and upgrade docs** | Partial | `docs/OFFLINE_INSTALL.md` and `release/.../QUICKSTART.md` exist. Add a single “Installation” section or doc that covers standard + offline and points to secure install where relevant. |

**Deliverables:** Signed artifacts, integrity verification doc, updated customer README, changelog, and clear install/upgrade path.

---

## 3. Support & Operations (should-have for commercial)

| Item | Status | Notes |
|------|--------|--------|
| **Support process** | Not done | Define how customers get help (email, portal, SLA). Document in README or a short “Support” doc (e.g. support email, link to docs, “how to open a ticket”). |
| **Support bundle for customers** | Done | `bin/hb support bundle` and `bin/hb support health` exist. Document in customer docs so users know how to collect diagnostics when contacting support. |
| **Runbook for your team** | Done | `docs/RUNBOOK.md`, `docs/INCIDENT_RESPONSE.md`, etc. Ensure runbook is updated for commercial (e.g. severity, escalation, customer comms). |
| **SLAs (optional)** | Not done | If you offer SLAs (e.g. response time, uptime for a hosted component), define and document them. Not required for a license-only, on-prem product. |

**Deliverables:** Support contact and process in README or support doc; runbook updated for commercial; optional SLA doc.

---

## 4. Security & Compliance (must-have for enterprise)

| Item | Status | Notes |
|------|--------|--------|
| **Threat model / security posture** | Not done | Production-readiness lists “Threat model + local-only security posture doc” as open. For commercial, add a short security doc: deployment model (local-only), data flow, what is not sent off-box, and recommended hardening. |
| **SBOM and vuln scanning** | Partial | SBOM/license scan and secure coding are in the rubric. For commercial: ship SBOM (or link) with each release and document that dependencies are scanned for known vulnerabilities. |
| **Secure install guidance** | Done | `docs/SECURE_INSTALL.md` exists. Include or reference it in the customer-facing kit/docs so security-conscious customers can follow it. |

**Deliverables:** Threat model or “Security posture” doc for customers; SBOM (or instructions) per release; reference to secure install in customer docs.

---

## 5. Product & Technical Gaps (from production-readiness)

These don’t block “giving it out” legally but affect **reliability and trust** for commercial use:

| Item | Status | Notes |
|------|--------|--------|
| **Performance guardrails** | Not done | Streaming logs, bounded memory. Prevents runaway resource use in customer environments. |
| **Evidence capture (asserts)** | Not done | Values, timestamps, offending segments for assertions. Improves debuggability and support. |
| **Threat model + security doc** | Done | See §4 above. |
| **Governance and ops** | Not done | 2–3 week closeout: baseline approval workflow, config versioning, invariant CI guard, performance benchmarks and tuning guidance. |

**Deliverables:** Address before or shortly after first commercial release, and document limits (e.g. max file size, recommended resources) in customer docs.

---

## 6. Optional: If You Offer a Hosted/SaaS Version

If “give out commercially” includes a **hosted multi-tenant offering**, use the checklist in `mvp/production-ready-commercial-saas.md` (tenant isolation, RBAC, SSO, compliance, SLAs, etc.). That is separate from shipping the current kit as licensed software.

---

## Summary: Minimum to Give It Out Commercially

**Implemented (complete before first ship):**

1. **Legal:** Commercial EULA template in `release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt`. **You must:** Replace placeholders; get legal review; confirm third-party license compatibility.
2. **Packaging:** Checksum generation (`tools/release_checksums.py`; `build_kit.py --checksums`); `docs/INTEGRITY_VERIFICATION.md`; customer README with install, license, support.
3. **Support:** `docs/SUPPORT.md` with process and support-bundle instructions; README links to it. **You must:** Set `[SUPPORT_EMAIL]` and `[SUPPORT_PORTAL_URL]` in SUPPORT.md.
4. **Security:** `docs/THREAT_MODEL_CUSTOMER.md`; README references SBOM and secure install; SECURE_INSTALL.md included in kit.

**Before you ship — replace placeholders:**

- In **README.md** and **LICENSE_COMMERCIAL.txt:** `[YEAR]`, `[COPYRIGHT HOLDER]`, `[JURISDICTION]`, and support/contact details.
- In **docs/SUPPORT.md:** `[SUPPORT_EMAIL]`, `[SUPPORT_PORTAL_URL]`.

**Should-have soon after:**

- Performance guardrails and documented limits.
- Governance/ops closeout (baseline workflow, config versioning, CI guards).

**Reference:** Existing production checklist: `production_checklist.md`. Field deployment: `docs/FIELD_DEPLOYMENT_V1.md`. Commercial SaaS (if applicable): `mvp/production-ready-commercial-saas.md`.
