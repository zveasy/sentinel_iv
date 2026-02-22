# Production HB DoD Roadmap

**Purpose:** Plan and track implementation of TRL-7+ operational capability for Harmony Bridge in DoD environments. “Production HB DoD” minimum bar is defined in §9.

**References:** `docs/PRODUCTION_READINESS_REVIEW.md`, `docs/PRODUCT_STATUS.md`, `docs/PREWG.md`, `docs/WAVEOS_INTEGRATION.md`.

---

## Phase Overview

| Phase | Focus | Dependencies |
|-------|--------|---------------|
| **P1** | Runtime mission assurance (streaming, actions, operational mode) | — |
| **P2** | Certification-grade baseline (quality gates, drift management, portability) | P1 |
| **P3** | Evidence, audit, non-repudiation (crypto chain, custody, replay) | P1 |
| **P4** | Security hardening (RBAC, KMS, supply chain) | P1, P3 |
| **P5** | Reliability, HA, observability, performance | P1 |
| **P6** | Integrations (system bus, WaveOS, test/lab) | P1, P2 |
| **P7** | Productization (dashboard, installer, runbooks) | P1–P5 |
| **P8** | V&V (determinism, fault injection, HIL/SIL demo) | P1–P7 |

---

## 1. Runtime Mission Assurance Layer

### 1.1 True streaming evaluator

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 1.1.1 | Event-time processing (late/out-of-order) + watermarks | Done | `hb/streaming/event_time.py` EventTimeClock, WatermarkPolicy; late_event_policy drop/buffer/side_output |
| 1.1.2 | Sliding windows (250ms / 1s / 10s) with incremental aggregates | Done | `hb/streaming/windows.py` SlidingWindowAggregator, WindowSpec; incremental buckets, no full recompute |
| 1.1.3 | Latency budgets in metrics (p50/p95 decision time) | Done | `hb/streaming/latency.py` LatencyRecorder; snapshot() for export |
| 1.1.4 | Deterministic decision snapshots (inputs + config → decision) | Done | `hb/streaming/snapshot.py` DecisionSnapshot; config_ref hashes, input_slice_ref, decision_payload |
| **Deliverable** | **hb runtime mode** | Done | CLI `hb runtime --config config/runtime.yaml`; `hb/streaming/evaluator.py` StreamingEvaluator |

### 1.2 Action / enforcement engine (closed loop)

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 1.2.1 | Policy-driven actions: notify, degrade, failover, abort, isolate, rate_limit, shutdown | Done | `hb/actions/` policy loader; action types; execution engine |
| 1.2.2 | Action acknowledgements + retries + idempotency keys | Done | Action ledger: idempotency_key, ack, retry_count, status |
| 1.2.3 | Safety gates (e.g. no hard-shutdown unless two independent conditions) | Done | Safety rules in policy; gate evaluation before execute |
| 1.2.4 | Simulation mode (dry-run; would have done output) | Done | `hb actions execute --dry-run`; would_have_done in output |
| **Deliverable** | **hb actions subsystem + action ledger** | Done | DB table `action_ledger`; `hb actions execute|list|ack` |

### 1.3 State machine for operational modes

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 1.3.1 | System states: startup, nominal, degraded, fallback, maintenance, test, emergency | Done | `hb/modes.py` OperationalMode enum; MODE_TRANSITIONS; can_transition(), transition_evidence() |
| 1.3.2 | Mode-aware thresholds/invariants and baseline selection | Done | metric_registry.mode_overrides; load_metric_registry(..., operating_mode=); baseline selection prefers same mode |
| 1.3.3 | Mode transition rules + evidence (who/what changed mode) | Done | ModeTransitionEvidence; transition_evidence() for audit |
| **Deliverable** | **operational_mode first-class** | Done | Schema/baseline/compare already use operating_mode; modes.py for state machine and evidence |

---

## 2. Baseline Assurance to “Certification-Grade”

### 2.1 Baseline quality gates

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 2.1.1 | Acceptance criteria: min sample size, time-in-state, stability (variance bounds), no unresolved alerts, env match score ≥ threshold | Done | `baseline_quality_policy.yaml`; gate evaluator; block tag if not met |
| 2.1.2 | Baseline confidence score (0–1) in decisions | Done | Score from criteria; “don’t enforce hard actions if confidence < X” in action policy |
| **Deliverable** | **Baseline isn’t just “tagged”** | — | `hb baseline set` runs quality gates; confidence in lineage and reports |

### 2.2 Baseline drift management

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 2.2.1 | Baseline decay detection (baseline itself stale) | Done | `hb/baseline_decay.py`: baseline_age_sec, check_baseline_decay (age + drift-from-current) |
| 2.2.2 | Controlled updates: rolling proposals → review → approval | Done | `hb baseline request` + `hb baseline approve`; governance in baseline_policy; audit in baseline_approvals/requests |
| 2.2.3 | Golden + rolling dual baseline | Done | `baseline_policy.yaml` dual_baseline.use_golden_for_hard_gates, use_rolling_for_early_warning; strategy rolling + baseline create/promote |
| **Deliverable** | **Dual baseline + decay + approval** | — | Policy options; UI/CLI for propose/approve |

### 2.3 Cross-platform baseline portability

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 2.3.1 | Equivalence mapping (vendor A ↔ vendor B sensor name/scale) | Done | `config/equivalence_mapping.yaml`; `hb/equivalence.py` load_equivalence_mapping, apply_equivalence |
| 2.3.2 | Unit conversions + calibration offsets with provenance | Partial | `docs/UNIT_CONVERSIONS_AND_CALIBRATION.md`; engine unit_map/_unit_convert; provenance in run_meta/baseline lineage |
| **Deliverable** | **Portable baselines** | — | Config + docs |

---

## 3. Evidence, Audit, and Non-Repudiation (DoD-grade)

### 3.1 Cryptographic evidence chain

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 3.1.1 | Signed reports (Ed25519 or org PKI) | Done | `--sign-key`; `docs/EVIDENCE_SIGNING.md` (Ed25519, org PKI, key formats) |
| 3.1.2 | Hash-chained audit log (each record hashes previous) | Done | `hb/audit.py` already chains; verify_audit_log |
| 3.1.3 | Signed config + metric registry snapshots | Done | Snapshot + sign on capture; store in evidence pack |
| 3.1.4 | Evidence manifest with hashes for every artifact | Done | `write_artifact_manifest`; extend to include config hashes in manifest |
| **Deliverable** | **Tamper-evident chain** | Done | Doc “Evidence and non-repudiation”; CI check chain |

### 3.2 Chain-of-custody workflows

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 3.2.1 | Case IDs, custody events (created, accessed, exported, transmitted) | Done | `custody_events` table; `custody_event_insert`, `custody_events_list`; `hb export evidence-pack --db [--operator-id]` records "exported" |
| 3.2.2 | Operator identity + reason codes (why promoted, why override) | Done | `--approved-by`, `--reason` in baseline approve/request; stored in `baseline_approvals`/`baseline_requests`; `docs/CUSTODY_AND_AUDIT.md` |
| 3.2.3 | Export controls: redaction profiles (PII/program-sensitive) | Done | `apply_redaction(..., profile=)`; `hb export evidence-pack --redaction-policy --redaction-profile`; policy YAML `profiles: { name: { redact: {...} } }` |
| **Deliverable** | **Custody + operator attribution** | — | Schema + runbook |

### 3.3 Defensible replay

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 3.3.1 | Replay decision: same input slice, config/registry version, code (SBOM-attested) | Done | `hb replay --input-slice --baseline --metric-registry`; replay_config_ref.json with hashes |
| 3.3.2 | Bit-for-bit match where feasible | Done | `tests/test_determinism.py`; `docs/DETERMINISM_AND_REPLAY.md` |
| **Deliverable** | **Replay CLI + tests** | — | `hb replay --input-slice ... --config-ref ...` |

---

## 4. Security Hardening for Production DoD

### 4.1 AuthN/AuthZ (RBAC)

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 4.1.1 | Roles: viewer, operator, approver, admin | Done | `hb/rbac.py` ROLES, has_permission, require_role; CLI enforces when HB_RBAC=1 (baseline set/approve, export evidence-pack, db encrypt/decrypt) |
| 4.1.2 | Per-program access (program partitions/tenants) | Done | `hb runs list --program <name>`; `HB_PROGRAM` env; `list_runs(conn, program=...)` in registry |
| 4.1.3 | API auth: mTLS + JWT/OPA or mTLS + signed tokens | Partial | `hb/auth_middleware.py` AuthConfig, check_request_auth, wrap_handler_with_auth; require_mtls + mtls_dn_header; full JWT/OPA at LB or extend |
| 4.1.4 | Break-glass override: tight logging + expiry | Done | `--break-glass --override-reason` on analyze/run; audit log `break_glass_override` with expires_at; RBAC when HB_RBAC=1 |
| **Deliverable** | **RBAC + program scope** | — | Schema + integration points |

### 4.2 Secrets & key management

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 4.2.1 | KMS integration (AWS KMS / Vault / optional HSM) | Done | `hb/keys.py` get_key_provider("kms"|"vault"); boto3/hvac optional; HB_KMS_* / HB_VAULT_* / VAULT_* env |
| 4.2.2 | Key rotation for signing keys | Done | `write_artifact_manifest(..., signing_key_version=)`; key version in manifest; runbook in KEY_MANAGEMENT.md |
| 4.2.3 | Encrypted DB at rest + encrypted evidence packs | Done | SQLCipher: `hb db encrypt/decrypt`; evidence: `--encrypt-key` on analyze/run; `docs/KEY_MANAGEMENT.md` |
| 4.2.4 | Secure defaults (no plaintext secrets in config) | Done | `hb/config_validation.py`; `HB_REJECT_PLAINTEXT_SECRETS=1`; reject plaintext at load |
| **Deliverable** | **KMS/Vault + rotation** | — | Docs + optional impl |

### 4.3 Supply chain security

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 4.3.1 | Reproducible builds | Done | `docs/REPRODUCIBLE_BUILDS.md` (lockfile, build script, PYTHONHASHSEED) |
| 4.3.2 | Signed container images | Partial | `docs/CONTAINER_SIGNING.md` (cosign/Notary; sign in CI, verify at deploy) |
| 4.3.3 | SBOM generation + verification gates in CI | Done | `tools/verify_sbom.py`; CI and release run verify after generate |
| 4.3.4 | Dependency pinning + vulnerability scanning | Partial | pip-audit in CI; pin in requirements |
| **Deliverable** | **CI gates + signed images** | — | CI + runbook |

---

## 5. Reliability, Operations, and Scaling

### 5.1 HA / resilience

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 5.1.1 | Exactly-once / effectively-once ingestion (idempotent) | Done | Idempotency keys on ingest; `--idempotency-key`; dedup via `hb/resilience.py` |
| 5.1.2 | Backpressure + circuit breakers | Done | `CircuitBreaker` in daemon (config `circuit_breaker`); open after N failures, skip cycle when open; stream backpressure optional |
| 5.1.3 | Failover: active/standby deployment pattern | Done | `docs/FAILOVER_HA.md` (active/standby, checkpoint sync, single-writer) |
| 5.1.4 | Persistent checkpoints (not just last cycle) | Done | Checkpoint history in `daemon_output/checkpoint_history/`; `save_checkpoint_to_history` |
| **Deliverable** | **Resilience doc + checkpoint format** | — | Implement where applicable |

### 5.2 Observability

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 5.2.1 | Prometheus: ingest lag, decision latency, baseline match, action success rate | Done | `hb/metrics_prometheus.py`; `hb health serve` exposes /metrics |
| 5.2.2 | Structured logs + correlation IDs | Done | `correlation_id` in run_meta and report payload; `HB_CORRELATION_ID` env |
| 5.2.3 | Tracing (OpenTelemetry) ingest → decision → action | Done | `hb/tracing.py` span(), trace_analyze(); no-op if opentelemetry-api not installed |
| 5.2.4 | Health: readiness/liveness + dependency health | Done | `hb health serve`; /ready, /live, /metrics |
| **Deliverable** | **Metrics + health endpoints** | — | Implement in runtime/daemon |

### 5.3 Performance engineering

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 5.3.1 | Streaming aggregator for large metric sets | Done | `SlidingWindowAggregator` incremental; optional `max_buckets` eviction; `hb/streaming/windows.py` |
| 5.3.2 | Benchmarks + regression tests in CI | Done | `tests/test_streaming_benchmark.py` (smoke, throughput, max_buckets); optional HB_STREAMING_BENCH_EVENTS / HB_STREAMING_BENCH_MAX_S |
| 5.3.3 | Configurable memory caps + safe degradation | Done | `docs/MEMORY_CAPS.md`; daemon window_sec + max_report_dir_mb; streaming `max_buckets` in runtime config |
| **Deliverable** | **Benchmarks + caps** | — | CI + docs |

---

## 6. Integrations (“Middleware”)

### 6.1 System bus

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 6.1.1 | Kafka / NATS / ZeroMQ adapters (in addition to MQTT/syslog) | Done | `hb/ingest/sources/kafka.py` KafkaSource; registered in ingest when confluent_kafka available |
| 6.1.2 | Binary telemetry (protobuf/flatbuffers) | Planned | Schema-driven decode; optional |
| 6.1.3 | Schema registry integration | Planned | Fetch schema by id/version for decode |
| **Deliverable** | **Kafka/NATS adapters** | — | At least one bus adapter |

### 6.2 WaveOS tight coupling

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 6.2.1 | Contract: HB → HEALTH_EVENT, DRIFT_EVENT, ACTION_REQUEST; WaveOS → ACTION_ACK, MODE_CHANGED, POLICY_APPLIED | Done | `docs/WAVEOS_CONTRACT.md`; WaveOS adapter in codebase |
| 6.2.2 | Rate-limited policy updates + staged rollout + rollback | Partial | `hb/policy_rate_limit.py` PolicyRateLimiter, PolicyRateLimitConfig; `docs/POLICY_RATE_LIMIT_AND_ROLLBACK.md` (version, staged rollout, rollback) |
| 6.2.3 | Policy provenance (who/what updated) | Done | `docs/POLICY_PROVENANCE.md`; config hashes in evidence; baseline_approvals/requests store approved_by, reason |
| **Deliverable** | **WaveOS contract + provenance** | — | Doc + adapter extensions |

### 6.3 Test system / lab integration

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 6.3.1 | Jenkins artifacts, lab controllers, NI/Keysight exports | Partial | Jenkins adapter in hb_core; extend as needed |
| 6.3.2 | Pre-flight gate in CI/CD (HB as release gate) | Done | `HB_GATE_FAIL_EXIT=1` → exit non-zero on FAIL; `docs/PRE_FLIGHT_GATE.md` |
| **Deliverable** | **Pre-flight gate doc + example** | — | CI job example |

---

## 7. Productization

### 7.1 Operator dashboard

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 7.1.1 | Live health + drift timeline | Planned | UI views; real-time or short-interval poll |
| 7.1.2 | Baseline match + confidence visualization | Planned | Charts + confidence badge |
| 7.1.3 | “Why flagged” driver breakdown + evidence links | Done | Report has investigation_hints + evidence_links (metric_name, artifact_ref, report_ref, hint) for UI to link to metrics/report |
| 7.1.4 | Case/evidence browser + chain-of-custody | Partial | `hb custody timeline --case <id>`, `hb custody list`; custody_events in DB; full UI planned |
| 7.1.5 | Overrides + approvals UI | Planned | Request/approve from UI |
| **Deliverable** | **War-room ready dashboard** | — | New or extend local UI |

### 7.2 Installer + deployment

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 7.2.1 | Linux package + systemd | Partial | deploy/install.sh + hb-daemon.service |
| 7.2.2 | Docker/Podman | Partial | Dockerfile exists |
| 7.2.3 | K8s Helm chart | Done | `helm/sentinel-hb/` (Deployment, Service, PVC, health sidecar) |
| 7.2.4 | Air-gapped install (offline + signed bundles) | Partial | OFFLINE_INSTALL.md; signed bundle path |
| **Deliverable** | **Helm + air-gap doc** | — | Artifacts + docs |

### 7.3 Documentation & runbooks

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 7.3.1 | Operator runbooks (alerts, actions, overrides) | Done | RUNBOOK.md (actions, modes, quality, decay, evidence pack, break-glass, redaction, custody timeline) |
| 7.3.2 | Admin guide (keys, RBAC, retention, HA) | Done | `docs/ADMIN_GUIDE.md` |
| 7.3.3 | Program onboarding (schema, registry, baseline workflow) | Done | `docs/PROGRAM_ONBOARDING.md` |
| **Deliverable** | **Runbooks + admin + onboarding** | — | Docs |

---

## 8. Verification & Validation

### 8.1 Verification suite for HB

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 8.1.1 | Determinism tests (same input → same decision) | Done | `tests/test_determinism.py` (compare_metrics deterministic, drift case) |
| 8.1.2 | Property-based tests (schema mappings, unit conversion) | Done | `tests/test_property_compare.py` (Hypothesis; compare deterministic, normalize_alias) |
| 8.1.3 | Golden test vectors for compare engine | Done | `tests/golden/compare_expected.json`; `tests/test_golden_compare.py` |
| 8.1.4 | Fault-injection library: time skew, missing telemetry, spikes, stuck-at, sensor drift, duplication | Done | `hb/inject/faults.py`: time_skew, stuck_at, spike, sensor_drift, duplication; CLI --fault all |
| **Deliverable** | **V&V test suite** | — | tests/vv/ or similar |

### 8.2 HIL / SIL demonstration

| # | Item | Status | Deliverable |
|---|------|--------|-------------|
| 8.2.1 | Reference testbed: sensor → broker → HB runtime → WaveOS stub → actuator | Done | `deploy/hil-testbed/docker-compose.yaml` (mosquitto, HB daemon, health, WaveOS stub) |
| 8.2.2 | Evidence pack for every run | Done | Daemon config `evidence_pack_always: true`; `docs/RUNBOOK.md`; default remains evidence on FAIL only |
| 8.2.3 | Acceptance test plan mapping to readiness gates | Done | `docs/ACCEPTANCE_TEST_PLAN.md` (trace matrix, gates, scenarios) |
| **Deliverable** | **HIL/SIL demo package** | — | Repo or doc |

---

## 9. “Production HB DoD” Definition (Minimum Bar)

TRL-7+ operational capability requires:

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Live ingest + streaming evaluator | In progress (P1.1) |
| 2 | Action/enforcement loop with acknowledgements | In progress (P1.2) |
| 3 | Baseline confidence + governance gates | In progress (P2.1) |
| 4 | Signed evidence + tamper-evident audit trail | Partial (audit chain done; signing exists) |
| 5 | RBAC + mTLS + key management | Planned (P4) |
| 6 | HA + observability + performance regression tests | Planned (P5) |
| 7 | Operator UX + deployment (air-gapped capable) | Partial (P7) |
| 8 | HIL demo + V&V pack | Planned (P8) |

**Definition of done for “Production HB DoD”:** All eight rows above implemented and documented; HIL demo runs repeatedly with evidence pack; V&V suite passes in CI.

---

## Implementation Order (Current Sprint)

1. **P1.1** — Streaming evaluator: event-time, watermarks, sliding windows, decision snapshots (foundation for runtime mode). **Done.**
2. **P1.2** — Actions subsystem: policy, action ledger DB, execute/list/ack, dry-run, safety gates. **Done.**
3. **P1.3** — Operational mode state machine: modes enum, mode-aware baseline/compare/reports. **Done.**
4. **P2.1** — Baseline quality gates: acceptance criteria config, confidence score, used in decisions. **Done.**
5. **P3.1** — Evidence: signed config snapshots, evidence manifest with all hashes; document chain. **Done.**

After this sprint, next priorities: P3.2 custody, P4.1 RBAC, P5.1/P5.2 HA and observability, then P6–P8.

---

## Implemented This Sprint (Summary)

- **docs/PRODUCTION_HB_DOD_ROADMAP.md** — Full roadmap with phases 1–9 and status table.
- **hb/streaming/** — EventTimeClock, WatermarkPolicy, SlidingWindowAggregator, WindowSpec, StreamingEvaluator, DecisionSnapshot, LatencyRecorder; **config/runtime.yaml**; CLI **hb runtime --config config/runtime.yaml**.
- **hb/actions/** — ActionPolicy, ActionEngine, ACTION_TYPES, safety_gate (require_two_conditions for shutdown/abort); **config/actions_policy.yaml**; **action_ledger** table; CLI **hb actions execute|list|ack** (with --dry-run).
- **hb/modes.py** — OperationalMode enum, MODE_TRANSITIONS, can_transition(), transition_evidence().
- **hb/baseline_quality.py** — load_baseline_quality_policy(), evaluate_baseline_quality() (acceptance criteria + confidence 0–1); **config/baseline_quality_policy.yaml**.
- **hb/audit.py** — write_artifact_manifest(..., config_hashes), write_config_snapshot_hashes(); analyze() writes config hashes into manifest.
- **Registry** — action_ledger_insert, action_ledger_ack, action_ledger_retry, action_ledger_list, action_ledger_by_idempotency.
