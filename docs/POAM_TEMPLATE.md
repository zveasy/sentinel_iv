# Plan of Action and Milestones (POA&M) — Template

**Purpose:** Vulnerability management workflow and POA&M template for tracking open findings and remediation.

**References:** `docs/COMPLIANCE_MATRIX.md`, `docs/SECURITY_POSTURE.md`, pip-audit, SBOM.

---

## 1. Vulnerability management workflow

1. **Identify:** Run `pip-audit` (and/or `pip install pip-audit && pip-audit`), SBOM verification, and any internal scan.
2. **Record:** Add finding to POA&M (below) with ID, control(s), description, severity, due date.
3. **Remediate:** Patch, upgrade, or mitigate; document in POA&M and in change control.
4. **Verify:** Re-run scan; close item when resolved.
5. **Review:** Periodic (e.g. monthly) POA&M review; escalate overdue critical/high.

---

## 2. POA&M template (table)

| POA&M ID | Control(s) | Finding | Severity | Due date | Status | Notes |
|----------|------------|---------|----------|----------|--------|------|
| 001 | SI-3, RA-5 | Dependency CVE-XXXX | High | YYYY-MM-DD | Open / Closed | Upgrade lib X to vY |
| … | | | | | | |

---

## 3. Severity and due dates

- **Critical:** 15 days or per program directive.
- **High:** 30 days.
- **Medium:** 90 days.
- **Low:** Next release or 180 days.

---

## 4. Evidence

- Retain scan output (pip-audit, SBOM verify) and POA&M in version control or artifact store.
- Link to COMPLIANCE_MATRIX control(s) for each finding.
