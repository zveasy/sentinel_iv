# Unit Conversions and Calibration Offsets with Provenance

Metric values may be converted to canonical units and adjusted by calibration offsets. Recording provenance (source units, conversion factor, calibration source) supports audit and portable baselines.

## Unit conversions

- **In-engine:** `hb/engine.py` uses `metric_registry["metrics"][name].unit_map` and `unit` (canonical) in `_unit_convert()`. Raw value × factor → canonical unit. No provenance is stored in the run today; the registry and run_meta are the implicit record.
- **Provenance:** To record that a conversion was applied, store in run_meta or baseline lineage (e.g. `conversion_provenance: [{ metric, from_unit, to_unit, factor, source: "metric_registry" }]`). Optional: add a small helper that appends to run_meta when `_unit_convert` actually changes the value, and persist that in the report or DB run row.

## Calibration offsets

- **Concept:** A sensor may have a known offset (e.g. +0.1°C) applied from a calibration run or vendor sheet. Store offset and source (e.g. `calibration_run_id`, `vendor_sheet_version`) with the baseline or run so replay and audit can show why a value was adjusted.
- **Implementation options:**
  - Add optional `calibration_offsets: { metric: { value: 0.1, unit: "C", source: "run:cal-2024-01", ts_utc: "..." } }` to run_meta or baseline metadata. In compare or normalize, add the offset after unit conversion when present.
  - Or keep calibration in the metric_registry as a per-metric default offset with a `calibration_provenance` string (e.g. "vendor_sheet_v2").

## Storing with baseline/run

- **Run:** `run_meta` (or a dedicated column in `runs`) can hold `conversion_provenance` and `calibration_offsets` as JSON. When writing run_meta_normalized.json or upserting the run, include these when the pipeline has applied conversions/calibration.
- **Baseline:** When setting a baseline from a run, lineage or baseline_versions can store the same so that downstream compare knows which conversions/calibration were in effect for that baseline.
