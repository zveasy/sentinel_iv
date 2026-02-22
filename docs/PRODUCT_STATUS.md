# Product Status: What the Repo Can Do vs. What’s Left for Commercial

**Last updated:** From current repo state and checklists.

---

## What This Repo Can Do Today

### Core analysis and reporting

- **Ingest** file-based sources: CSV, Excel (PBA), NASA HTTP TSV, SMAP/MSL, CMAPSS, custom tabular. `hb ingest --source <source> <path> --out <dir>`.
- **Analyze** a run vs. a baseline: drift detection (threshold + percent), critical fails, invariants, optional distribution drift (KS). `hb analyze --run <artifact_dir>` or `hb run` (ingest + analyze).
- **Compare** two artifacts (e.g. two CSVs) with optional auto-schema. `hb compare --baseline <path> --run <path> --out <dir>`.
- **Plan runs** from YAML: multiple scenarios, requirement traceability, trace matrix export, trend. `hb plan run <plan.yaml>`.
- **Reports:** HTML, JSON, optional PDF; “why flagged” narrative, top drivers, diff visualizations, trend charts, baseline match level.
- **Investigation hints:** Every report includes **What to do next** and per-metric **pinpoint + suggested actions** (root-cause category, re-baseline vs. fix). CLI prints a short “what to do next” line after each analyze.

### Baseline and registry

- **Baseline governance:** Tag a run as baseline (`hb baseline set <run_id> --tag golden`), list tags, request/approve workflow (optional policy).
- **Run registry:** SQLite store of runs, metrics, baseline lineage; config and policy hashes for matching.
- **Metric registry:** Versioned metrics, thresholds, invariants, aliases, unit normalization; config validation.

### Packaging and operations

- **Build release kit:** `python tools/build_kit.py [--checksums]` → versioned zip + optional `.sha256` and `checksums.txt`. Kit includes customer docs (threat model, integrity verification, support, secure install, offline install, changelog).
- **Integrity verification:** `docs/INTEGRITY_VERIFICATION.md` + `tools/release_checksums.py`; customers verify the zip before install.
- **Support tooling:** `hb support health`, `hb support bundle`; documented in `docs/SUPPORT.md`.
- **Audit and signing:** Artifact manifests, audit log, optional `--sign-key` / `--encrypt-key` for reports; redaction policy.

### Demo and tests

- **Quick demo:** `./tools/demo.sh` runs baseline + current (single_metric_drift), prints report path and “what to do next,” optionally opens the drift report.
- **Tests:** Unit tests (engine, report, investigation), compare API tests, optional CMAPSS regression when `CMAPSS_ROOT` set; CI runs pytest.

### Commercial-facing assets (implemented but not yet “released”)

- **Commercial EULA template:** `release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt` (placeholders to replace + legal review).
- **Customer README:** System requirements, install (standard/offline/secure), license, support, security; placeholders in README and SUPPORT.
- **Threat model for customers:** `docs/THREAT_MODEL_CUSTOMER.md` (local-only, no exfil, hardening).
- **Placeholder check:** `python tools/check_release_placeholders.py` fails if `[YEAR]`, `[COPYRIGHT HOLDER]`, `[SUPPORT_EMAIL]`, etc. remain in release files.

---

## What’s Left for the Product to Be Commercial

### 1. Commercial “go-to-market” (legal, branding, support)

| Item | Status | What to do |
|------|--------|------------|
| **Commercial EULA in use** | Template only | Replace all placeholders in `LICENSE_COMMERCIAL.txt` and customer README; get legal review; use this license (not eval) for paid distribution. |
| **Support contact** | Template only | Set `[SUPPORT_EMAIL]` and `[SUPPORT_PORTAL_URL]` in `docs/SUPPORT.md`; document in README. |
| **Third-party licenses** | Partial | Audit `artifacts/licenses.json` (and any “Non-Commercial” deps); confirm compatibility with commercial use and document. |
| **Optional: GPG signing** | Not done | Sign release zips and document verification in release notes; integrity today is checksums only. |

**Deliverable:** No unreplaced placeholders (`check_release_placeholders.py` passes), legal sign-off on EULA, and a real support channel.

---

### 2. “Pilot-ready” software (before buying hardware)

The repo is **demo-ready** (file-based ingest, analyze, report) but not yet **pilot-ready** (live telemetry, 24/7 daemon, alerts, evidence automation). The gap is described in `docs/PILOT_2WEEK_SPRINT.md`. Summary of what’s **not** implemented:

| Area | Missing | Deliverable (from sprint plan) |
|------|--------|--------------------------------|
| **Live telemetry ingestion** | MQTT, syslog, file-replay | `hb ingest --source mqtt\|syslog\|file-replay` |
| **Telemetry normalization** | Schema + unit/name mapping | `config/telemetry_schema.yaml` + `hb normalize` |
| **Baseline training** | Time-window baseline, versioning, promote | `hb baseline create --window 24h`, `hb baseline promote` |
| **Continuous mode** | Daemon, rolling windows | `hb daemon` + config; systemd unit |
| **Alerting** | Sinks for drift/FAIL | `hb alert --sink stdout\|file\|webhook` (or daemon-integrated) |
| **Evidence packs** | Auto on FAIL, export | `hb export evidence-pack --case <id>` |
| **Fault injection** | For demos without hardware | `hb inject --fault latency_spike\|value_corruption\|...` |
| **Resilience** | Checkpointing, disk caps | Daemon survives restart; bounded disk |
| **Deployment hardening** | Non-root, locked-down unit | `deploy/install.sh` + systemd hardening |

**Definition of “pilot-ready”:** `hb daemon` runs 24h with simulated (or real) telemetry, builds baseline, detects drift, emits alerts and evidence pack, and survives restart. Until then, buying hardware is higher risk.

---

### 3. Optional (soon after commercial or later)

- **Performance guardrails:** Streaming logs, bounded memory; document max file size / resource limits.
- **Assert evidence capture:** Values, timestamps, offending segments for assertion failures.
- **Governance closeout:** Baseline approval workflow docs, config versioning script, invariant CI guard.
- **WaveOS integration:** Event schema and adapter (see `docs/WAVEOS_INTEGRATION.md` placeholder).
- **SaaS/hosted:** If you offer a hosted product, see `mvp/production-ready-commercial-saas.md` (separate from shipping the kit as licensed software).

---

## One-line summary

- **Today:** The repo can ingest file-based data, compare runs to a baseline, detect drift and fails, produce HTML/JSON/PDF reports with “what to do next” and investigation hints, manage baselines and a run registry, build a commercial-style kit with docs and checksums, and run a quick demo—but it has **no live telemetry connectors, no daemon, no alerting, and no evidence-pack automation**.
- **To be commercial (legal):** Replace all release placeholders, get legal review of the EULA, and set a real support contact.
- **To be commercial (pilot):** Implement the 2-week sprint (connectors, daemon, baseline create/promote, alerting, evidence pack, resilience, install hardening) so the product can run 24h on a laptop with simulated telemetry and then on real hardware with low risk.

---

## What's next (implementation priorities)

**1. Commercial ship (legal / trust)**  
- Replace placeholders: `[YEAR]`, `[COPYRIGHT HOLDER]`, `[SUPPORT_EMAIL]`, `[SUPPORT_PORTAL_URL]` in `release/hb-hybrid-kit/README.md`, `LICENSE_COMMERCIAL.txt`, `docs/SUPPORT.md`.  
- Legal review of EULA; set real support channel.  
- Audit `artifacts/licenses.json` for commercial use; document.  
- Optional: SBOM in release workflow; GPG signing of release zips.

**2. Technical / product (soon after)**  
- **Evidence capture for asserts:** values, timestamps, offending segments when assertions fail (RITS parity).  
- **Performance guardrails:** streaming logs, bounded memory; document max file size and resource limits.  
- **Baseline evolution modes:** golden, last-known-good, rolling median/quantile.  
- **Governance closeout:** baseline approval workflow docs, config versioning script, invariant CI guard (see 2–3 week closeout in `mvp/production-readiness.md`).

**3. Optional / follow-on**  
- **PREWG:** Program readiness gates (Pre-CDR, Pre-Flight, etc.); see `docs/PREWG.md`.  
- **WaveOS:** Event schema in `schemas/waveos_events.json`; adapter TODO in `docs/WAVEOS_INTEGRATION.md`.  
- **SaaS/hosted:** Use checklist in `mvp/production-ready-commercial-saas.md` if offering a hosted product.

**References:** `docs/COMMERCIAL_RELEASE_CHECKLIST.md`, `docs/PRODUCTION_READINESS_REVIEW.md`, `docs/PILOT_2WEEK_SPRINT.md`, `mvp/production-readiness.md`.
