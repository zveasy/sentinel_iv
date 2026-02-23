# V&V Test Procedures and Expected Results

**Purpose:** Step-by-step procedures and expected results for the formal V&V package. Use with `docs/VV_TEST_PLAN.md` and `docs/VV_ACCEPTANCE_CRITERIA.md`.

---

## Q1. Telemetry drop

**Objective:** Verify HB handles partial or full loss of telemetry without crash and with predictable status.

### Procedure

1. Prepare a baseline run: ingest a known-good CSV/Excel to `runs/baseline/`.
2. Create a “current” run from the same source but **drop a subset of rows** (e.g. remove 30% of rows or all rows for one metric).
3. Run `hb analyze --run runs/current` (or `hb run` for ingest+analyze).
4. Capture: exit code, report status (PASS / PASS_WITH_DRIFT / FAIL), report JSON/HTML.

### Expected results

- HB does not crash (exit 0 or 2/3/4 per contract).
- Report is generated; status reflects policy (e.g. FAIL if critical metric missing or threshold violated).
- Missing or insufficient data for a metric is indicated in report (e.g. “insufficient data”, low confidence, or metric omitted).
- Audit log and artifact manifest are written.

### How to induce drop

- Manually trim input CSV; or use fault injector that drops rows by metric (extend `hb/inject/faults.py` with `drop_metric_rows(rows, metric, pct=0.3)` if needed). Procedure can use a pre-made sample in `samples/` (e.g. `samples/cases/telemetry_drop/`).

---

## Q2. Delayed packets (out-of-order)

**Objective:** Verify event-time and watermark handling when events arrive late.

### Procedure

1. Use streaming runtime or daemon with a short window (e.g. 10 s).
2. Feed events with **time_skew**: some events have timestamp in the past (e.g. `time_skew(rows, skew_seconds=-30)` so they appear “late”).
3. Run runtime or daemon for one or two window flushes.
4. Capture: decision output, any side output or late-event log.

### Expected results

- No crash. Late events are either dropped or sent to side output per `late_event_policy` in config.
- Decision is based on watermark; may not include late events. Documented in `docs/REALTIME_GUARANTEES.md` and streaming event_time.

### How to induce

- Use `hb/inject/faults.py` `time_skew()` on a replay file or synthetic stream; or replay a recorded stream with modified timestamps.

---

## Q3. Corrupted data

**Objective:** Verify HB handles invalid or out-of-range values without unhandled exception.

### Procedure

1. Take a valid baseline run. Create current run with **value_corruption** (e.g. large noise or NaN/blank for some values) or manually insert invalid numbers/strings.
2. Run `hb ingest` then `hb analyze` (or `hb run`).
3. Capture: exit code, report, any validation errors in logs.

### Expected results

- No unhandled exception. Ingest or compare may reject invalid rows or emit validation errors (exit 2 or 3).
- If compare runs, report may show drift or fail on affected metrics; data quality issue should be visible in report or logs.

### How to induce

- `value_corruption(rows, noise_scale=10.0)` or insert a row with `value: "not_a_number"` in CSV; run ingest and analyze.

---

## Q4. Conflicting signals

**Objective:** Verify status and report when two (or more) metrics disagree (one OK, one FAIL).

### Procedure

1. Use a run where **one metric** is set to fail (e.g. beyond threshold) and **another** remains at baseline.
2. Run `hb analyze --run <artifact_dir>`.
3. Check report: status should be FAIL (if any critical metric fails); report should list both metrics with correct pass/fail/drift for each.

### Expected results

- Overall status = FAIL when any metric is in fail set (per engine logic).
- Report lists all metrics; failed metric(s) and passing metric(s) are both visible with correct attribution.
- No single-metric dominance hiding the other; both signals appear in “top drift” or metric list as appropriate.

### How to induce

- Use `stuck_at` or `spike` on one metric only; leave others unchanged. Or use two baselines/run pairs crafted so one metric drifts and one does not.

---

## Q5. Stuck-at / spike (fault injection)

**Objective:** Verify drift detection when a metric is stuck or spiked.

### Procedure

1. Baseline: ingest normal run to `runs/baseline/`.
2. Current: apply `stuck_at(rows, metric="M1", value=100)` or `spike(rows, metric="M1", scale=3.0)` to same source, ingest to `runs/current/`.
3. Run `hb analyze --run runs/current`.
4. Capture: status, report; confirm M1 is flagged.

### Expected results

- Status PASS_WITH_DRIFT or FAIL depending on thresholds.
- Report flags M1 with drift/fail; investigation hints point to that metric.
- Fault injectors are deterministic enough for repeatable test (or document seed).

### How to induce

- `hb/inject/faults.py`: `stuck_at`, `spike`, `sensor_drift`, `duplication`. Use in test script or CLI `--fault` if wired.

---

## Q6. Baseline decay

**Objective:** Verify baseline decay detection when baseline is old or no longer representative.

### Procedure

1. Set a baseline from an old run (or use baseline_decay logic with age threshold).
2. Run current analyze with baseline_decay checks enabled (if configured).
3. Capture: report or logs for decay warning; confidence or “baseline stale” indication.

### Expected results

- When baseline age or drift-from-current exceeds policy, decay is reported (see `hb/baseline_decay.py`). Report or lineage may show baseline_confidence or decay warning.
- No crash; behavior documented in RUNBOOK and baseline_decay.

---

## Generic procedure template (unit/integration)

1. **Setup:** Clean DB or dedicated DB path; load config (metric_registry, baseline_policy).
2. **Execute:** Run CLI or API (ingest, analyze, compare, actions execute).
3. **Capture:** Exit code, stdout/stderr, report files, DB state.
4. **Evaluate:** Compare to expected results in this doc and VV_ACCEPTANCE_CRITERIA.
5. **Record:** Log procedure ID, date, result (pass/fail), evidence path.

---

## References

- Fault injectors: `hb/inject/faults.py`
- Determinism: `tests/test_determinism.py`
- Golden compare: `tests/test_golden_compare.py`
- Acceptance criteria: `docs/VV_ACCEPTANCE_CRITERIA.md`
