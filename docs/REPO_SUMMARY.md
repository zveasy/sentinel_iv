# Sentinel-IV / Harmony Bridge — Repo Summary

**Last updated:** From current repo state and docs.

This document gives an overall summary of the repository: what it is, what’s implemented, and what it can do. For product/commercial status and gaps, see [PRODUCT_STATUS.md](PRODUCT_STATUS.md). For the DoD production roadmap, see [PRODUCTION_HB_DOD_ROADMAP.md](PRODUCTION_HB_DOD_ROADMAP.md).

---

## 1. What This Repo Is

- **Sentinel-IV™** — A defense-focused verification and instrumentation platform that ensures real hardware behavior stays consistent with certified baselines across integration, test, and sustainment.
- **Harmony Bridge (HB)** — The software-only MVP inside this repo: a system-agnostic **drift detection and health-assurance layer**. It does not run tests; it consumes exported artifacts (Excel/CSV/JSON, telemetry) and compares current runs to baselines to detect behavioral drift and produce evidence.

**In one line:** Post-test analysis and live-runtime assurance that compare telemetry/runs to baselines, detect drift and failures, and produce reports, evidence packs, and (optionally) closed-loop actions.

---

## 2. Repo Layout (High Level)

| Area | Purpose |
|------|--------|
| **`hb/`** | Core Harmony Bridge: CLI, engine, ingest, compare, report, registry, streaming, actions, daemon, auth, RBAC, audit, etc. |
| **`hb/ingest/`** | Ingest pipeline and sources: file (CSV/Excel/PBA, NASA TSV, SMAP/MSL, CMAPSS, custom), MQTT, syslog, Kafka, file-replay. |
| **`hb/streaming/`** | Streaming evaluator: event-time, watermarks, sliding windows, decision snapshots, latency recording. |
| **`hb/actions/`** | Policy-driven actions (notify, degrade, failover, abort, isolate, rate_limit, shutdown), ledger, safety gates, dry-run. |
| **`hb/alerting/`** | Alert sinks: stdout, file, webhook. |
| **`hb/adapters/`** | Data adapters: PBA Excel, CMAPSS FD001–004, NASA HTTP TSV, SMAP/MSL, custom tabular. |
| **`hb/inject/`** | Fault injection: time_skew, stuck_at, spike, sensor_drift, duplication (for demos/V&V). |
| **`config/`** | Example configs: thresholds, baseline policy, metric registry, runtime, actions policy, baseline quality, equivalence. |
| **`docs/`** | All product, DoD, security, and operational documentation. |
| **`tools/`** | Build kit, demo, SBOM, checksums, retention, backup, CI helpers. |
| **`samples/`** | Sample cases (no_drift_pass, single_metric_drift, etc.), synthetic data scripts. |
| **`tests/`** | Unit, golden, property-based, determinism, streaming benchmark, real-data regression. |
| **`deploy/`** | systemd, Docker, HIL testbed (docker-compose). |
| **`helm/`** | Kubernetes Helm chart for Sentinel HB. |
| **`release/`** | Release kit layout (README, QUICKSTART, license template). |
| **`mvp/`** | MVP notes, production-readiness, acceptance criteria. |

---

## 3. What’s Implemented

### 3.1 Ingest and Analysis

- **File-based ingest:** CSV, Excel (PBA), NASA HTTP TSV, SMAP/MSL, CMAPSS FD001–004, custom tabular.
- **Live/streaming ingest:** MQTT, syslog, Kafka (when deps available), file-replay.
- **Commands:** `hb ingest --source <source> <path> --out <dir>`, optional `--stream`; `hb run` (ingest + analyze in one).
- **Analysis:** Drift detection (threshold + percent), critical fails, invariants, optional distribution drift (KS). `hb analyze --run <artifact_dir>` or via `hb run`.
- **Compare:** Two artifacts (e.g. two CSVs) with optional auto-schema: `hb compare --baseline <path> --run <path> --out <dir>`.
- **Plan runs:** YAML plans with multiple scenarios, requirement traceability, trace matrix export, trend: `hb plan run <plan.yaml>`.

### 3.2 Reports and Investigation

- **Reports:** HTML, JSON, optional PDF; “why flagged” narrative, top drivers, diff visualizations, trend charts, baseline match level.
- **Investigation:** Every report has “What to do next” and per-metric pinpoint + suggested actions (root-cause category, re-baseline vs fix). CLI prints a short “what to do next” after analyze.

### 3.3 Baseline and Registry

- **Baseline governance:** Tag run as baseline (`hb baseline set <run_id> --tag golden`), list tags, request/approve workflow (optional policy).
- **Run registry:** SQLite store of runs, metrics, baseline lineage; config and policy hashes for matching.
- **Metric registry:** Versioned metrics, thresholds, invariants, aliases, unit normalization; config validation.
- **Baseline quality gates:** Acceptance criteria (min sample size, time-in-state, stability, etc.), confidence score (0–1); `config/baseline_quality_policy.yaml`.
- **Baseline decay:** Detection of stale baseline; `hb/baseline_decay.py`.
- **Dual baseline:** Golden + rolling; policy-driven (e.g. golden for hard gates, rolling for early warning).
- **Equivalence mapping:** Cross-platform baseline portability (vendor A ↔ B sensor name/scale); `config/equivalence_mapping.yaml`, `hb/equivalence.py`.

### 3.4 Streaming and Runtime

- **Streaming evaluator:** Event-time processing, watermarks, late-event policy; sliding windows (e.g. 250ms / 1s / 10s) with incremental aggregates; latency budgets (p50/p95); deterministic decision snapshots.
- **Runtime mode:** `hb runtime --config config/runtime.yaml`; `StreamingEvaluator` in `hb/streaming/evaluator.py`.

### 3.5 Actions and Operational Mode

- **Actions:** Policy-driven (notify, degrade, failover, abort, isolate, rate_limit, shutdown); action ledger (idempotency, ack, retries); safety gates (e.g. two independent conditions for shutdown/abort); simulation: `hb actions execute --dry-run`.
- **Operational modes:** States (startup, nominal, degraded, fallback, maintenance, test, emergency); mode-aware thresholds/baseline selection; mode transition rules and evidence; `hb/modes.py`.

### 3.6 Evidence, Audit, and Security

- **Signed reports:** `--sign-key`; Ed25519 or org PKI; `docs/EVIDENCE_SIGNING.md`.
- **Hash-chained audit log:** Each record hashes previous; `hb/audit.py`, `verify_audit_log`.
- **Evidence manifest:** Hashes for artifacts and config snapshots; evidence pack export.
- **Custody:** Case IDs, custody events (created, accessed, exported, transmitted); operator identity and reason codes; export with redaction profiles.
- **Replay:** `hb replay --input-slice --baseline --metric-registry`; replay_config_ref with hashes; determinism tests.
- **RBAC:** Roles (viewer, operator, approver, admin); per-program access; break-glass override with logging and expiry; `HB_RBAC=1`.
- **Keys and secrets:** KMS (AWS/Vault) integration, key rotation, encrypted DB (SQLCipher), encrypted evidence packs; secure defaults (reject plaintext secrets in config).
- **Redaction:** Policy YAML profiles; `hb export evidence-pack --redaction-policy --redaction-profile`.

### 3.7 Packaging, Support, and Deployment

- **Release kit:** `python tools/build_kit.py [--checksums]` → versioned zip + optional checksums; customer docs (threat model, integrity verification, support, secure install, offline install).
- **Support:** `hb support health`, `hb support bundle`; `docs/SUPPORT.md`.
- **Install/deploy:** `deploy/install.sh`, systemd unit; Dockerfile; Helm chart `helm/sentinel-hb/`; offline/air-gap docs.
- **SBOM and supply chain:** Reproducible builds doc; SBOM generation and `tools/verify_sbom.py`; container signing doc.

### 3.8 Resilience and Observability

- **Resilience:** Idempotent ingest; circuit breakers in daemon; failover (active/standby) doc; checkpoint history.
- **Observability:** Prometheus metrics (ingest lag, decision latency, baseline match, action success); structured logs and correlation IDs; OpenTelemetry tracing (optional); health server: `hb health serve` (/ready, /live, /metrics).
- **Performance:** Streaming aggregator with optional `max_buckets`; memory caps docs; streaming benchmarks in CI.

### 3.9 Integrations and Productization

- **System bus:** Kafka (and optionally NATS/ZeroMQ) adapters.
- **WaveOS:** Contract (HEALTH_EVENT, DRIFT_EVENT, ACTION_REQUEST, etc.); adapter; policy rate limit and provenance.
- **Pre-flight gate:** `HB_GATE_FAIL_EXIT=1` for CI/CD release gate; `docs/PRE_FLIGHT_GATE.md`.
- **Runbooks and docs:** `RUNBOOK.md`, `ADMIN_GUIDE.md`, `PROGRAM_ONBOARDING.md`.
- **HIL testbed:** `deploy/hil-testbed/` docker-compose (mosquitto, HB daemon, health, WaveOS stub).

### 3.10 Verification and Fault Injection

- **Determinism:** Same input → same decision; `tests/test_determinism.py`.
- **Property-based tests:** Schema mappings, unit conversion; `tests/test_property_compare.py`.
- **Golden tests:** Compare engine; `tests/golden/`, `tests/test_golden_compare.py`.
- **Fault injection:** `hb/inject/faults.py` — time_skew, stuck_at, spike, sensor_drift, duplication; CLI `--fault`.

### 3.11 UI and Workflows

- **Local Web UI:** `hb ui` → http://127.0.0.1:8890/; workspace, baseline, analyze/compare, report, support bundle, watch folder.
- **Watch folder:** `hb watch --dir <path> --source pba_excel --pattern "*.csv" --interval <sec>` for periodic drift checks.
- **Feedback loop:** Local feedback server and UI; Correct / Too Sensitive / Missed Severity; export summary/raw; `hb feedback serve`, `hb feedback export`.

---

## 4. What It Can Do (User-Facing)

- **Ingest** file or live telemetry → normalized metrics and optional events.
- **Analyze** a run vs a baseline → PASS / PASS_WITH_DRIFT / FAIL with explanations.
- **Compare** two artifacts (e.g. CSVs) with optional schema.
- **Plan** multi-scenario runs from YAML with traceability and trend.
- **Produce** HTML/JSON/PDF reports with “what to do next” and per-metric investigation hints.
- **Manage baselines:** set, list, request, approve; quality gates and confidence; decay detection; dual (golden + rolling) strategy.
- **Run streaming runtime** with event-time windows and decision snapshots.
- **Execute actions** from policy (notify, degrade, failover, etc.) with ledger, ack, and dry-run.
- **Track operational mode** and use mode-aware thresholds and baselines.
- **Export evidence packs** with optional redaction and encryption; custody timeline.
- **Sign and encrypt** reports and DB; use KMS/Vault for keys.
- **Serve health and metrics** for Prometheus and ops.
- **Run as a daemon** with configurable cycle, checkpoints, and alerting.
- **Demo in ~30 seconds** via `./tools/demo.sh` (baseline + current, open drift report).
- **V&V:** Determinism, golden tests, property-based tests, fault injection, HIL testbed.

---

## 5. Quick Commands Reference

| Command / flow | Purpose |
|----------------|--------|
| `bin/hb run --source pba_excel <csv> --run-meta <meta.json>` | One-shot ingest + analyze. |
| `bin/hb ingest --source <source> <path> --out <dir>` | Ingest only. |
| `bin/hb analyze --run <artifact_dir>` | Analyze run vs baseline. |
| `bin/hb compare --baseline <path> --run <path> --out <dir>` | Compare two artifacts. |
| `bin/hb plan run <plan.yaml>` | Run plan with scenarios. |
| `bin/hb baseline set <run_id> --tag golden` | Tag baseline. |
| `bin/hb baseline request / approve / list` | Governance. |
| `bin/hb runtime --config config/runtime.yaml` | Streaming runtime. |
| `bin/hb actions execute \| list \| ack` | Actions (add `--dry-run` for simulate). |
| `bin/hb daemon` | Run daemon (config-driven). |
| `bin/hb health serve` | Health + Prometheus. |
| `bin/hb ui` | Local Web UI. |
| `bin/hb watch --dir <path> --source pba_excel ...` | Watch folder. |
| `bin/hb export evidence-pack ...` | Export evidence with optional redaction. |
| `bin/hb replay --input-slice ...` | Defensible replay. |
| `./tools/demo.sh` | Quick drift demo. |

---

## 6. Key Documentation

| Doc | Content |
|-----|--------|
| [README.md](../README.md) | Project overview, business context, CLI quickstart, UI, Docker, samples. |
| [PRODUCT_STATUS.md](PRODUCT_STATUS.md) | What the repo can do today vs what’s left for commercial and pilot. |
| [PRODUCTION_HB_DOD_ROADMAP.md](PRODUCTION_HB_DOD_ROADMAP.md) | DoD production phases (P1–P8), implementation status, definition of “Production HB DoD”. |
| [RUNBOOK.md](RUNBOOK.md) | Operator runbooks: actions, modes, quality, decay, evidence pack, break-glass, redaction, custody. |
| [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | Keys, RBAC, retention, HA. |
| [PROGRAM_ONBOARDING.md](PROGRAM_ONBOARDING.md) | Schema, registry, baseline workflow. |
| [PILOT_2WEEK_SPRINT.md](PILOT_2WEEK_SPRINT.md) | Gap to pilot-ready (live telemetry, daemon, alerting, evidence automation). |
| [SYSTEM_INTEGRATION.md](SYSTEM_INTEGRATION.md) | Hard system integration: HB_EVENT contract, C++/SDK, telemetry buses, deterministic guarantees. |
| [REALTIME_GUARANTEES.md](REALTIME_GUARANTEES.md) | Latency targets, load testing (10k+ metrics/sec), backpressure, degradation strategy. |
| [COMPLIANCE_MATRIX.md](COMPLIANCE_MATRIX.md) | NIST 800-53 and RMF control mapping for certification. |
| [VV_TEST_PLAN.md](VV_TEST_PLAN.md), [VV_TEST_PROCEDURES.md](VV_TEST_PROCEDURES.md), [VV_ACCEPTANCE_CRITERIA.md](VV_ACCEPTANCE_CRITERIA.md) | Formal V&V package: test plan, procedures, acceptance criteria, qualification scenarios. |
| [DECISION_AUTHORITY.md](DECISION_AUTHORITY.md) | Confidence-based action gating and multi-signal validation. |
| [OPERATOR_TRUST.md](OPERATOR_TRUST.md) | Confidence scores, historical accuracy, FP/FN tracking. |
| [WAVEOS_CLOSED_LOOP.md](WAVEOS_CLOSED_LOOP.md) | Full HB ↔ WaveOS loop, bidirectional sync, control hierarchy. |
| [PRODUCT_BOUNDARY.md](PRODUCT_BOUNDARY.md) | Product layers: Core, Runtime, Ops, DoD Package. |
| [FIRST_DEPLOYMENT_CHECKLIST.md](FIRST_DEPLOYMENT_CHECKLIST.md) | Checklist for first real deployment (live system proof). |
| [REFERENCE_INTEGRATIONS.md](REFERENCE_INTEGRATIONS.md) | Lab harness, Kafka/NATS, prime-like system integration. |
| [PERFORMANCE_ENVELOPE.md](PERFORMANCE_ENVELOPE.md) | Published envelope (X events/sec, p99 latency); backpressure; fail-safe. |
| [ACTION_TIERS.md](ACTION_TIERS.md) | Action tiers (0–3), break-glass, baseline approval governance. |
| [SSP_LITE.md](SSP_LITE.md) | System Security Plan (lite) for reviewers. |
| [POAM_TEMPLATE.md](POAM_TEMPLATE.md) | POA&M template and vulnerability management workflow. |
| [STIG_SECURE_CONFIG.md](STIG_SECURE_CONFIG.md) | STIG-aligned secure configuration guide. |
| [SLSA_BUILD_PROVENANCE.md](SLSA_BUILD_PROVENANCE.md) | SBOM and signed build provenance (SLSA-ish). |
| [MULTI_TENANT.md](MULTI_TENANT.md) | Program partitions, per-program RBAC/retention, export/import enclaves. |
| [DEPLOYMENT_OS_AND_UPGRADES.md](DEPLOYMENT_OS_AND_UPGRADES.md) | OS support matrix, deterministic installers, upgrade/migration path. |
| [PILOT_REPORT_TEMPLATE.md](PILOT_REPORT_TEMPLATE.md) | Pilot report template (value, adoption, metrics). |
| [FIRST_RUN_WIZARD.md](FIRST_RUN_WIZARD.md) | First-run wizard and UX design (30-min onboarding). |
| [CHANGELOG.md](../CHANGELOG.md) | Version history and release notes. |

---

## 7. One-Line Summary

**This repo** implements Harmony Bridge: ingest (file + live), baseline comparison, drift and invariant detection, streaming runtime, action/enforcement engine, operational modes, baseline quality and governance, evidence and custody, RBAC and key management, reports with investigation hints, local UI and watch folder, daemon and health endpoints, fault injection and V&V — with a path to commercial (legal/support) and pilot-ready (connectors, daemon, alerting, evidence automation) described in PRODUCT_STATUS and the DoD roadmap.
