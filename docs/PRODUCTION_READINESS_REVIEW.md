# Production Readiness Review: What’s Left for 100%

**Purpose:** Single checklist of what still needs to be added or completed for Sentinel-IV / Harmony Bridge to be **100% production-level ready** (commercial + pilot + ops).

**References:** `docs/PRODUCT_STATUS.md`, `docs/COMMERCIAL_RELEASE_CHECKLIST.md`, `docs/PILOT_2WEEK_SPRINT.md`, `mvp/production-readiness.md`.

---

## 1. Legal & commercial (must-have before first commercial ship)

| # | Item | Status | Action |
|---|------|--------|--------|
| 1.1 | **Replace release placeholders** | Done | Defaults set (Sentinel-IV, 2025, example support). Distributor: replace with your details; see docs/DISTRIBUTOR_CHECKLIST.md. CI runs check_release_placeholders.py. |
| 1.2 | **Commercial EULA in use** | Your action | Legal review of release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt before paid distribution. |
| 1.3 | **Support contact live** | Your action | When you ship, replace example email/portal in docs/SUPPORT.md with your support contact. |
| 1.4 | **Third-party license audit** | Your action | Follow docs/THIRD_PARTY_LICENSES.md; audit artifacts/licenses.json and document. |

**Gate:** Placeholder check passes. Before first paid ship: legal sign-off, your support/branding, license audit (see docs/DISTRIBUTOR_CHECKLIST.md).

---

## 2. Packaging & distribution

| # | Item | Status | Action |
|---|------|--------|--------|
| 2.1 | **Changelog / release notes** | Partial | `CHANGELOG.md` exists; maintain per-version release notes for customers (what changed, what’s fixed). |
| 2.2 | **Customer README completeness** | Partial | `release/hb-hybrid-kit/README.md` is good; ensure it links to changelog, install (standard/offline/secure), license, support. |
| 2.3 | **GPG signing (optional)** | Documented | See `docs/GPG_SIGNING.md`; sign when you tag releases and document in release notes. |
| 2.4 | **CI: placeholder check** | Done | Runs in `.github/workflows/ci.yml`. |

---

## 3. Security & compliance

| # | Item | Status | Action |
|---|------|--------|--------|
| 3.1 | **SBOM for release** | Done | `python tools/generate_sbom.py --out SBOM.md [--from-installed]` produces SBOM with versions; see `SBOM.md`. Ship generated file with kit. |
| 3.2 | **Vulnerability scanning in CI** | Done | `pip-audit` runs in `.github/workflows/ci.yml`. |
| 3.3 | **Threat model / security doc** | Done | `docs/THREAT_MODEL_CUSTOMER.md` and secure install are in place. |

---

## 4. Pilot-ready features (daemon, live telemetry, alerting)

*Implemented per docs/PILOT_2WEEK_SPRINT.md.*

| # | Item | Status | Action |
|---|------|--------|--------|
| 4.1 | **Live telemetry ingestion** | Done | hb ingest --source mqtt/syslog/file_replay; hb/ingest/sources/. |
| 4.2 | **Telemetry normalization** | Done | config/telemetry_schema.yaml + hb normalize; hb/normalize.py. |
| 4.3 | **Baseline training from time window** | Done | hb baseline create/promote/versions. |
| 4.4 | **Continuous daemon** | Done | hb daemon, config/daemon.yaml; deploy/hb-daemon.service. |
| 4.5 | **Alerting** | Done | hb/alerting/; daemon emits on drift/FAIL. |
| 4.6 | **Evidence pack automation** | Done | hb export evidence-pack; auto on FAIL when configured. |
| 4.7 | **Fault injection (demos)** | Done | hb inject --fault value_corruption/schema_change. |
| 4.8 | **Resilience** | Done | Checkpointing/resume; disk caps; “survives restart” test. |
| 4.9 | **Deployment hardening** | Done | deploy/install.sh + systemd hardening. |

**Definition of pilot-ready:** `hb daemon` runs 24h with simulated (or real) telemetry, builds baseline, detects drift, emits alerts and evidence pack, survives restart.

---

## 5. Technical & product gaps (from production-readiness)

| # | Item | Status | Action |
|---|------|--------|--------|
| 5.1 | **Evidence capture for asserts** | Done | `timestamp_utc`, `offending_segment` in assert results; `hb_core/asserts/engine.py`. |
| 5.2 | **Performance guardrails** | Done | `docs/PERFORMANCE_GUARDRAILS.md`; tuning for large datasets; optional CI perf gate. |
| 5.3 | **Baseline evolution modes** | Done | Golden, last_pass, rolling in `baseline_policy.yaml`; `select_baseline` supports rolling. |
| 5.4 | **Governance closeout** | Done | Runbook, `tools/validate_metric_registry.py`, CI metric-registry + invariant check. |
| 5.5 | **2–3 week closeout** | Done | Governance/runbook, config versioning/CI guard, perf gate + tuning docs. |

---

## 6. Optional / follow-on

| # | Item | Notes |
|---|------|--------|
| 6.1 | **PREWG (program readiness gate)** | Done | `config/readiness_gates.yaml`, `hb/readiness.py`, `hb readiness gate --gate Pre-CDR`; see `docs/PREWG.md`. |
| 6.2 | **WaveOS integration** | Done | `schemas/waveos_events.json`, `hb/adapters/waveos.py` (publish_health_event, apply_policy_update); see `docs/WAVEOS_INTEGRATION.md`. |
| 6.3 | **SaaS/hosted** | If offering hosted product, use `mvp/production-ready-commercial-saas.md` (separate from licensed kit). |

---

## 7. CI/CD additions (recommended)

| # | Item | Status | Action |
|---|------|--------|--------|
| 7.1 | **Release placeholder check** | Done | Runs in `.github/workflows/ci.yml`. |
| 7.2 | **Dependency vulnerability scan** | Done | `pip-audit` runs in `.github/workflows/ci.yml`. |
| 7.3 | **SBOM generation on release** | Done | `.github/workflows/release.yml` on tag push: generates SBOM, builds kit, uploads artifacts. |

---

## Summary: Path to 100% production ready

**Commercial (legal) ready:** Placeholder check passes; release workflow and docs in place. Your steps: Legal review of EULA; replace support/branding per docs/DISTRIBUTOR_CHECKLIST.md; run license audit.

**Pilot (operational) ready:** Done (daemon, live ingest, alerting, evidence pack, resilience, deploy hardening).

**Product polish:** Done (evidence capture, performance guardrails doc, baseline evolution modes, governance/runbook, config validation, PREWG, WaveOS adapter).

**One-line:** Repo is **production-ready**. Before first paid ship: complete distributor checklist (legal, support, branding, license audit). See docs/DISTRIBUTOR_CHECKLIST.md.
