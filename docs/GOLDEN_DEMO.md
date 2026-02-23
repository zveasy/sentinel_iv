# Golden Demo Scenario

One perfect demo story for sales and program leads: baseline (clean) → second run (PASS with subtle drift) → third run (FAIL). HB flags drift early, escalates, triggers action request, generates evidence, and trust dashboard shows accuracy.

## Run the demo

```bash
./tools/run_golden_demo.sh [--out-dir /path]
```

Default output: `golden_demo_output/` (DB, reports).

## Story

1. **Baseline run (clean)**  
   Ingest `samples/cases/no_drift_pass/current_source.csv`. Result: **PASS**. Set as baseline (tag: golden).

2. **Second run (subtle drift)**  
   Ingest `samples/cases/single_metric_drift/current_source.csv`. Result: **PASS_WITH_DRIFT**. HB detects drift; no hard fail.

3. **Third run (FAIL)**  
   Ingest `samples/cases/reset_triggered_fail/current_source.csv`. Result: **FAIL**. HB flags drift, escalates, can trigger action request and generate evidence pack.

## After the demo

- **Evidence pack**:  
  `hb export evidence-pack --case <run_id> --report-dir <report_dir> --out golden_demo_output/evidence_packs --zip`
- **Verify decision**:  
  `hb verify-decision --decision <report_dir>/decision_record.json --evidence <evidence_pack_dir>`
- **Trust dashboard**:  
  `hb trust` (after recording feedback; optional for demo)

This flow is what closes deals: deterministic, auditable, and evidence-ready.
