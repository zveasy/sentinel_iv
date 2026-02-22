# Pre-Flight Gate: HB as a Release Gate in CI/CD

Use Harmony Bridge as a release or deployment gate: the pipeline runs HB compare and fails the build if the result is FAIL (or if drift exceeds a threshold).

## Exit codes

- `0` — success (PASS or PASS_WITH_DRIFT, depending on policy).
- `1` — unknown error.
- `2` — parse/ingest error.
- `3` — config error.
- `4` — registry error.

For **release gate:** run `hb analyze --run <artifact_dir>` (or `hb run` after ingest). Set **`HB_GATE_FAIL_EXIT=1`** so that when status is FAIL the CLI exits with code 2 (`PLAN_EXIT_FAIL`). Without this env, the CLI exits 0; with it, FAIL causes a non-zero exit for CI.

## Example: fail build on FAIL

```bash
# In your CI (e.g. Jenkins, GitLab CI):
hb run --source pba_excel "$CURRENT_RUN_CSV" --run-meta run_meta.json
STATUS=$(jq -r '.status' mvp/reports/<run_id>/drift_report.json)
if [ "$STATUS" = "FAIL" ]; then
  echo "HB gate failed: status=$STATUS"
  exit 1
fi
```

## Report artifact

Publish `mvp/reports/<run_id>/drift_report.json` (and optionally HTML) as pipeline artifacts so reviewers can see why a run failed. Optionally attach the evidence pack when status is FAIL.

## Readiness gates

For program-level gates (Pre-CDR, Pre-Flight, etc.), use `hb readiness gate --gate <name>`. The command exits 0 only when the gate verdict is Ready. Use in a separate job or after analyze to block release when the gate is not ready.
