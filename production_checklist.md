# Production Readiness Checklist (Phased)

## Phase 1: Baseline Governance + Adapter Hardening (now)

Baseline governance:
- Add baseline tag table to `runs.db`
- `hb baseline set <run_id> --tag <name>`
- `hb baseline list`
- Baseline selection supports tag override in `baseline_policy.yaml`
- Warn on metric registry mismatch when selecting baseline

Adapter hardening:
- Adapter handles CSV and Excel robustly with clear error messages
- Multiple-sheet Excel support (find first sheet with Metric/Current columns)
- Alias-based column resolution for Metric/Current/Value/Unit
- Explicit errors for missing required columns

Acceptance:
- Baseline tag can be set and used in `hb analyze`
- Report includes `baseline_reason` and `baseline_warning` if mismatch
- Adapter works for common PBA table variants without code changes

## Phase 2: Report Quality + Ops UX

- Report template with “why flagged” narrative
- PDF export option
- CLI prints report path and baseline info
- Exit codes standardized for CI
- Add a `bin/hb runs list` command to show recent runs from `runs.db`

## Phase 3: Reliability + Performance

- Large file handling and streaming ingest
- Deterministic outputs, idempotent runs
- Robust retry/transaction handling in SQLite

## Phase 4: Security + Compliance (if needed)

- Encryption at rest for registry and reports
- Signed artifacts and audit log
- SBOM and dependency pinning policy
