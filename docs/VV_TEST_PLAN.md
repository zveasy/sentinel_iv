# V&V Test Plan — Formal Validation Package

**Purpose:** Provide a repeatable, documented way to prove that Harmony Bridge works for DoD and certification. This is the **Test Plan** of the formal V&V package. Test Procedures and Expected Results are in `docs/VV_TEST_PROCEDURES.md`; Acceptance Criteria in `docs/VV_ACCEPTANCE_CRITERIA.md`.

**References:** `docs/ACCEPTANCE_TEST_PLAN.md`, `docs/PRE_FLIGHT_GATE.md`, `tests/`, `hb/inject/faults.py`.

---

## 1. Scope

- **In scope:** Core compare engine, ingest, baseline selection, reporting, actions, streaming evaluator, evidence and audit, fault injection, determinism, and qualification scenarios (telemetry drop, delayed packets, corrupted data, conflicting signals).
- **Out of scope:** Third-party infrastructure (MQTT broker, Kafka); OS and network; customer-specific metrics.

---

## 2. Test levels

| Level | Purpose | Artifacts |
|-------|--------|-----------|
| **Unit** | Engine, report, investigation, compare API, actions, streaming | pytest in `tests/`; coverage optional |
| **Integration** | Ingest → compare → report → registry; daemon cycle; actions + ledger | pytest; `tools/demo.sh`; daemon run |
| **Qualification** | Fault scenarios: telemetry drop, delayed packets, corrupted data, conflicting signals | Procedures in VV_TEST_PROCEDURES; expected results documented |
| **Performance** | Throughput, latency, memory caps | `tests/test_streaming_benchmark.py`; `tools/benchmark_streaming.py` |
| **Determinism** | Same input + config → same decision | `tests/test_determinism.py`; `hb replay` |
| **Regression** | Golden vectors; CMAPSS/NASA/SMAP-MSL when data available | `tests/test_golden_compare.py`; `tests/real_data/` |

---

## 3. Qualification scenarios (summary)

These scenarios answer: “How does HB behave when things go wrong?”

| ID | Scenario | Description | Procedure ref | Expected result |
|----|----------|-------------|---------------|-----------------|
| Q1 | Telemetry drop | Partial or full loss of telemetry for a window | VV_TEST_PROCEDURES §Q1 | Graceful handling; missing metrics reported; no crash; status PASS or PASS_WITH_DRIFT or FAIL per policy |
| Q2 | Delayed packets | Events arrive late (out-of-order) | VV_TEST_PROCEDURES §Q2 | Event-time/watermark handling; late events dropped or side output per config |
| Q3 | Corrupted data | Invalid or out-of-range values in stream | VV_TEST_PROCEDURES §Q3 | Validation/rejection or flag; no unhandled exception; report indicates data issue |
| Q4 | Conflicting signals | Two metrics disagree (e.g. one says OK, one FAIL) | VV_TEST_PROCEDURES §Q4 | Status reflects policy (e.g. FAIL if any critical fails); report shows both |
| Q5 | Stuck-at / spike | One metric stuck or spiked (fault injection) | VV_TEST_PROCEDURES §Q5 | Drift detected; report flags metric; fault injectors used in test |
| Q6 | Baseline decay | Baseline is old or no longer representative | VV_TEST_PROCEDURES §Q6 | Decay detection when enabled; confidence or warning in report |

---

## 4. Traceability

- **Requirements → Tests:** Map program or system requirements to test procedures (maintain in VV_ACCEPTANCE_CRITERIA or separate trace matrix).
- **Gates:** Pre-CDR, Pre-Flight, Regression-Exit, Release — see `docs/ACCEPTANCE_TEST_PLAN.md`. Each gate has a set of tests that must pass.
- **Evidence:** Test runs produce logs, reports, and (for qualification) evidence packs. Store in CI artifacts or V&V evidence repository.

---

## 5. Environment and tools

- **CI:** pytest, optional coverage; env vars for optional benchmarks and real-data regression.
- **Local:** Python 3.x; `pip install -r hb/requirements.txt -r hb/requirements-dev.txt`; `bin/hb` and `hb` CLI.
- **Fault injection:** `hb/inject/faults.py` (time_skew, stuck_at, spike, sensor_drift, duplication); use in procedures to drive Q2, Q3, Q5.

---

## 6. Approval and revisions

- **Approval:** Test plan and procedures should be reviewed and approved per program or quality process.
- **Revisions:** Document changes in this doc or a change log; keep version/date in header.

**Document version:** 1.0  
**Last updated:** From repo state.
