# MVP Acceptance Criteria

Core proof points:
1. Ingest at least one lab output format (Excel or CSV or logs).
2. Reduce raw data into 5-10 repeatable health metrics.
3. Compare a run to a baseline and flag drift even when tests PASS.
4. Generate artifacts: run health report + diff vs baseline + one-line summary.

Minimum inputs:
- One "known-good" baseline run output file.
- One "current" run output file.

Minimum outputs:
- Run health report (HTML or Excel or PDF).
- Baseline diff artifact (JSON).
- Summary string: PASS, PASS-with-drift, or FAIL.

Demonstration criteria:
- Run A and Run B both PASS by test criteria.
- Run B shows drift in at least two metrics.
- Tool labels Run B as PASS-with-drift and shows metric deltas.
