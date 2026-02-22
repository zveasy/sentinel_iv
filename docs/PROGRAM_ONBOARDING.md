# Program Onboarding Checklist

Use this when bringing a new program or test context into Harmony Bridge.

1. **Schema and metric registry**
   - Define or reuse `metric_registry.yaml`: metrics, thresholds, invariants, aliases, units.
   - If the program has distinct modes, add `mode_overrides` for nominal/degraded/etc. (see config).
   - Validate: `python tools/validate_metric_registry.py` (and add to CI if desired).

2. **Baseline policy**
   - Set `baseline_policy.yaml`: strategy (last_pass, tag, rolling, golden), context_match, governance (approval), dual_baseline if needed.
   - Ensure `operating_mode` and other context fields are in run_meta so baseline selection matches.

3. **Baseline creation**
   - Ingest a set of known-good runs (same program/subsystem/test_name).
   - Run baseline quality check (optional): ensure acceptance criteria in `config/baseline_quality_policy.yaml` are met.
   - Set tag: `hb baseline set <run_id> --tag golden` (or use request/approve if governance is on).
   - For rolling: `hb baseline create --window 24h` then `hb baseline promote --version <id> --tag rolling`.

4. **Equivalence (if cross-platform)**
   - If baseline was produced on a different platform/vendor, configure `config/equivalence_mapping.yaml` (metric name/scale mapping) and use when comparing.

5. **Run and verify**
   - Run `hb run` or `hb analyze` for a current run; confirm baseline is selected and report shows expected match level and confidence.
   - Optionally run `hb readiness gate --gate Pre-CDR` (or your gate) to confirm readiness.
