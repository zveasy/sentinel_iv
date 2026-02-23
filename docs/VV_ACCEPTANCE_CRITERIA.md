# V&V Acceptance Criteria

**Purpose:** Define the acceptance criteria that must be met for the formal validation package. Use with `docs/VV_TEST_PLAN.md` and `docs/VV_TEST_PROCEDURES.md`.

**References:** `docs/ACCEPTANCE_TEST_PLAN.md`, `docs/PRE_FLIGHT_GATE.md`.

---

## 1. Functional acceptance criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| AC-1 | Ingest accepts configured sources (CSV, Excel/PBA, NASA TSV, etc.) and produces normalized metrics. | Unit/integration tests; ingest of sample files. |
| AC-2 | Analyze produces status PASS, PASS_WITH_DRIFT, or FAIL consistent with metric thresholds and invariants. | Golden compare; determinism tests; manual runs. |
| AC-3 | Report includes baseline_run_id, baseline_confidence, correlation_id, top drift drivers, and “What to do next”. | Report schema and content checks; Pre-Flight gate. |
| AC-4 | Baseline set/list/request/approve work; quality gate blocks low-quality baseline when enabled. | Baseline tests; readiness gate Pre-CDR. |
| AC-5 | Actions (notify, degrade, etc.) are proposed and recorded per policy; safety gate blocks critical actions without two independent conditions. | Action engine tests; dry-run and execute. |
| AC-6 | Evidence pack export produces manifest and artifacts; optional signing and redaction. | Export tests; INTEGRITY_VERIFICATION. |
| AC-7 | Replay with same input slice and config produces same decision. | `tests/test_determinism.py`; `hb replay`. |
| AC-8 | Fault injection (telemetry drop, delayed packets, corrupted data, conflicting signals, stuck-at, spike) is covered by procedures and expected results. | VV_TEST_PROCEDURES Q1–Q6; run and record. |

---

## 2. Qualification scenario acceptance

| Scenario | Pass criterion |
|----------|----------------|
| Q1 Telemetry drop | HB completes without crash; report reflects missing/insufficient data; status per policy. |
| Q2 Delayed packets | Late events handled per config (drop/side output); no crash. |
| Q3 Corrupted data | No unhandled exception; validation or drift reported. |
| Q4 Conflicting signals | Status FAIL when any critical fails; both metrics visible in report. |
| Q5 Stuck-at / spike | Drift detected and reported for affected metric. |
| Q6 Baseline decay | Decay warning or confidence when baseline is stale (when enabled). |

---

## 3. Performance and robustness

| ID | Criterion | Verification |
|----|-----------|--------------|
| AC-P1 | Streaming benchmark runs (throughput, max_buckets); optional CI threshold. | `tests/test_streaming_benchmark.py`; REALTIME_GUARANTEES. |
| AC-P2 | Batch analyze of large file (e.g. 50k rows) completes within documented time. | `tools/benchmark_streaming.py`; document in runbook. |
| AC-P3 | Memory and disk are bounded by config (max_buckets, window_sec, max_report_dir_mb). | MEMORY_CAPS; config and docs. |
| AC-P4 | Circuit breaker opens after N failures; daemon skips cycle when open. | Daemon tests; FAILOVER_HA. |

---

## 4. Security and compliance

| ID | Criterion | Verification |
|----|-----------|--------------|
| AC-S1 | Audit log is hash-chained; verify_audit_log passes. | Audit tests; CUSTODY_AND_AUDIT. |
| AC-S2 | With HB_REJECT_PLAINTEXT_SECRETS=1, config with plaintext secrets is rejected. | Config validation tests. |
| AC-S3 | RBAC (when HB_RBAC=1) restricts baseline approve and evidence export to appropriate roles. | RBAC tests; ADMIN_GUIDE. |
| AC-S4 | SBOM generation and verification pass in CI/release. | `tools/verify_sbom.py`; RELEASE_CHECKLIST. |

---

## 5. Definition of “V&V complete”

- **Test Plan** approved and under change control.
- **Test Procedures** (VV_TEST_PROCEDURES) executed for all qualification scenarios (Q1–Q6) and results recorded.
- **Acceptance criteria** (this document) all met or explicitly waived with rationale.
- **Evidence** retained: test logs, report artifacts, and (where applicable) evidence packs for qualification runs.
- **Traceability:** Requirements (or gates) mapped to procedures and results; see ACCEPTANCE_TEST_PLAN trace matrix.

---

## 6. Waivers and deviations

- Any acceptance criterion not met must be documented with a **waiver** or **deviation**: identifier, rationale, risk, and approval.
- Re-test after fix and close waiver when criterion is met.
