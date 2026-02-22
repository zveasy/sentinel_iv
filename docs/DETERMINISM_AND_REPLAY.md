# Determinism and Defensible Replay

## Replay CLI

To replay a decision with the same inputs and config:

```bash
hb replay --input-slice <path to metrics CSV or run dir> \
  --baseline <path to baseline metrics or run_id> \
  --metric-registry metric_registry.yaml \
  [--baseline-policy baseline_policy.yaml] \
  [--db runs.db] \
  --out replay_output
```

- **Input slice:** Path to `metrics_normalized.csv` or a run directory containing it (or a JSON metrics file).
- **Baseline:** Path to baseline metrics CSV/dir, or a `run_id` if `--db` is provided (metrics are loaded from the DB).
- **Config ref:** The tool hashes the metric registry and baseline policy and writes `replay_config_ref.json` in `--out`. Use the same registry/policy versions to get a reproducible result.

Output: same compare result (status, drift_metrics, etc.) and a report in `--out`.

## Bit-for-bit and limitations

- **Determinism:** The compare engine is deterministic for a given (current metrics, baseline metrics, registry). Floating-point order and rounding can differ across Python versions or platforms; for strict bit-for-bit, run on the same platform and Python version and avoid platform-dependent code in the hot path.
- **Replay:** Replay uses the same code path as analyze. Differences can still arise if: (1) registry or policy file contents differ, (2) input slice or baseline metrics differ (e.g. CSV parsing), (3) environment (e.g. `HB_DETERMINISTIC`, `HB_EARLY_EXIT`) differs. Document the environment and config refs when attesting a replay.
- **SBOM:** For “same code” attestation, use the SBOM generated at release and the same dependency versions when replaying.
