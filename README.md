# sentinel_iv

## Overview of Business

Sentinel-IV(TM) is a defense-focused verification and instrumentation platform that ensures real hardware behavior remains consistent with previously certified baselines throughout system integration, test, and sustainment. Unlike virtual simulation tools, Sentinel-IV(TM) operates alongside existing DoD test infrastructure to automatically reduce, analyze, and compare real-hardware telemetry after each test run, generating standardized evidence artifacts for engineers, quality assurance, and program leadership. The company mission is to eliminate late-stage surprises caused by undetected hardware drift, reduce No-Fault-Found investigations, and improve confidence in test results for mission-critical defense systems.

## Problem Solved

Modern DoD systems generate massive volumes of test data during lab, HIL, and integration testing. While most builds pass formal test criteria, subtle degradation in timing margins, power integrity, reset behavior, or RF conditions often goes undetected until late integration or sustainment phases.

Current problems include:
- PASS/FAIL tests that lack behavioral context
- Manual, inconsistent post-test analysis (MATLAB/Excel heroics)
- Loss of institutional knowledge over time
- Expensive No-Fault-Found investigations
- Schedule slips caused by late discovery of drift

Virtual simulation tools validate logic correctness but cannot observe real hardware behavior. As a result, programs lack a continuous, automated method to confirm that "passing" hardware is still healthy relative to a trusted baseline.

## Product or Services Offered

Sentinel-IV(TM) is a passive, non-intrusive verification platform that integrates with existing DoD test environments.

Core capabilities:
- Automatic reduction of raw test telemetry into a small, predefined set of health metrics
- Baseline comparison against last known-good hardware runs
- Detection of behavioral drift even when tests pass
- Generation of standardized artifacts (reports, Excel summaries, audit logs)
- Commit-to-test traceability for configuration accountability

Sentinel-IV(TM) does not control tests, replace simulators, or modify hardware behavior. It operates as an observer and assurance layer.

## Market Overview

The DoD invests billions annually in system integration, verification, and sustainment across:
- Missile defense
- Radar and sensors
- Avionics
- Space systems
- Autonomous platforms

Late-stage integration failures and No-Fault-Found investigations routinely cost hundreds of thousands of dollars per event, yet current tools focus on test execution rather than test outcome assurance. The initial beachhead market is Systems Test, IV&V, and Mission Assurance organizations within DoD primes and government labs. These groups are responsible for evidence quality, auditability, and long-term system confidence.

Business model:
- Annual software license per lab or program
- Optional secure appliance deployment for classified environments
- Support and customization contracts for program-specific metrics

Revenue scales with:
- Number of programs
- Number of test environments
- Sustainment duration

This model aligns with long program lifecycles and recurring DoD funding profiles.

## Customers or Prospective Customers

Initial and prospective customers include:
- Raytheon (RTX) Systems Test & Mission Assurance groups
- Other DoD prime contractors (Lockheed Martin, Northrop Grumman, Boeing Defense)
- Government test centers and warfare centers
- Missile Defense Agency integration labs
- Air Force and Navy system verification organizations

## Sales and Marketing Strategy

Public sector focus:
- SBIR Phase I/II engagements with DoD components
- Pilot deployments within government or prime contractor labs
- Direct engagement with IV&V and Mission Assurance leadership

Adoption strategy:
- Demonstrate value by preventing one late-stage investigation
- Emphasize zero disruption to existing workflows
- Position as risk reduction infrastructure, not a new test tool

## Competitive Environment

Existing tools include:
- Virtual simulation platforms (e.g., SIMICS)
- Test automation frameworks
- Data acquisition and logging systems

However:
- These tools focus on test execution, not behavioral continuity
- No existing solution enforces automated baseline comparison of real hardware behavior across runs
- Most programs rely on manual analysis and tribal knowledge

Sentinel-IV(TM) complements existing tools rather than replacing them.

## Management Team

Zakariya Veasy -- Founder and Lead Engineer
Background in embedded software, systems integration, and defense software engineering. Experience operating within regulated defense environments and understanding verification, sustainment, and mission assurance workflows.

Additional advisors and contracted contributors will include:
- Systems Test Engineers
- QA / Mission Assurance professionals
- Secure systems software consultants

## Harmony Bridge (Software-Only MVP)

Harmony Bridge is a system-agnostic drift detection layer. It does not run tests; it consumes exported artifacts (Excel/CSV/JSON logs) and compares current runs to baselines.

Quickstart:
```
python -m venv .venv
source .venv/bin/activate
pip install -r hb/requirements.txt -r hb/requirements-dev.txt

chmod +x bin/hb
bin/hb ingest --source pba_excel samples/cases/no_drift_pass/current_source.csv --run-meta samples/cases/no_drift_pass/current_run_meta.json --out runs/no_drift_pass_current
bin/hb analyze --run runs/no_drift_pass_current
```

Commands:
```
bin/hb ingest --source pba_excel <path-to-file> --run-meta <run_meta.json> --out runs/<run_id>/
bin/hb analyze --run runs/<run_id>/ --baseline-policy baseline_policy.yaml
bin/hb run --source pba_excel <path-to-file> --run-meta <run_meta.json>
bin/hb baseline set <run_id> --tag golden
bin/hb baseline list
bin/hb analyze --run runs/<run_id>/ --pdf
bin/hb runs list --limit 20
bin/hb ingest --source pba_excel <path-to-file> --run-meta <run_meta.json> --stream
```

Exit codes:
- `0` success
- `1` unknown error
- `2` parse/ingest error
- `3` config error
- `4` registry error

Artifacts:
- `run_contract.md` describes `run_meta.json`, `metrics.csv`, and optional `events.jsonl`.
- Reports are written to `mvp/reports/<run_id>/` as `drift_report.json` and `drift_report.html`.
- Optional PDF export uses `wkhtmltopdf` if installed (`drift_report.pdf`).
- If `wkhtmltopdf` is not available, a pure-Python fallback uses `fpdf2`.

Streaming examples:
```
bin/hb ingest --source pba_excel samples/cases/no_drift_pass/current_source.csv --run-meta samples/cases/no_drift_pass/current_run_meta.json --out runs/no_drift_pass_current --stream
bin/hb run --source pba_excel samples/cases/no_drift_pass/current_source.csv --run-meta samples/cases/no_drift_pass/current_run_meta.json --stream
```

Synthetic demo:
```
python tools/make_synthetic_runs.py --baseline-count 3 --drift-count 3 --out samples/synthetic
chmod +x tools/run_synthetic_demo.sh
tools/run_synthetic_demo.sh
```

Large XLSX stress test:
```
python tools/make_large_xlsx.py --rows 50000 --out samples/large/large_pba.xlsx
bin/hb ingest --source pba_excel samples/large/large_pba.xlsx --run-meta samples/cases/no_drift_pass/current_run_meta.json --stream
```

Tests:
```
pytest -q
```

## MVP Acceptance Criteria

Done means:
- One-command flow works: `bin/hb run --source pba_excel samples/.../input.csv`
- Creates `mvp/reports/<run_id>/drift_report.html` and `mvp/reports/<run_id>/drift_report.json`
- Writes `runs.db` and stores run + metrics
- Baseline is automatically selected (last PASS for same program/subsystem/test_name)
- Baseline governance is available via `bin/hb baseline set/list`
- Alias mapping works when headers change
- Missing metrics do not crash the run
- All 8 golden tests pass

## Adapter Samples

- Unit-sheet Excel example: `samples/pba_unit_sheet_example.xlsx`
- Large XLSX generator: `python tools/make_large_xlsx.py --rows 50000 --out samples/large/large_pba.xlsx`

## Software-Only MVP Direction

Yes, a software-only MVP is the right move. It proves the core value without new hardware by delivering an observer + reducer + baseline comparer + report generator. Hardware becomes Phase II polish, not Phase I proof.

What this MVP proves:
- It can ingest outputs the lab already produces (MATLAB Excel, CSV, logs)
- It can reduce raw data into a repeatable set of health metrics
- It can compare a run to a baseline and flag drift even when PASS

Required inputs:
- One run output file (Excel/CSV/logs/telemetry dump)
- One known-good baseline output file

Outputs:
- Run health report (Excel/HTML/PDF)
- Diff vs baseline (JSON)
- One-line summary: PASS / PASS-with-drift / FAIL

Simple pipeline:
1. Ingest: load Excel/CSV/logs
2. Reduce: extract 5-10 metrics + event counts
3. Compare: baseline + thresholds
4. Report: generate an artifact
5. Store: save by run ID

Five-metrics strategy:
- Reset count / watchdog triggers
- Rail-bit or power warning count
- Max/avg latency of a key task
- Error code frequency
- Missed timing deadlines count
- RF noise floor proxy (if logged)
- State-transition anomalies count

Demo story:
- Run A (baseline): known-good PASS
- Run B: also PASS but with subtle drift
- Tool reports PASS-with-drift and highlights changes

Two-week build scope:
- Week 1: ingest Excel/CSV, feature extraction, baseline compare, report generation, CLI (`analyze --run <file> --baseline <file>`)
- Week 2: run registry (SQLite/JSON), trend chart, YAML thresholds, report polish

Hardware can wait unless:
- Lab outputs lack required signals
- Deeper observability is needed (power rails, RF, timing probes)
- A hardened appliance is required for classified environments

Internal one-liner:
This is a software-only post-test analysis layer that consumes existing outputs and standardizes evidence plus drift detection; hardware is optional later.

## Internal Lab MVP: Usability Addendum

The current internal-lab MVP is strong enough to pilot, but to make it usable by other engineers (not just "works on my machine"), add the following must-haves and a small set of optional upgrades.

### Required to avoid pilot failure

1) Data contract per source
- Add `mvp/schemas/<source_name>.yaml` (or JSON schema)
- Add `--source <name>` flag
- Define required/optional columns and defaults
- Acceptance: invalid input shows a single, explicit fix message

2) Baseline strategy aligned with lab reality
- `sentinel baseline set <run-id> --tag golden`
- `sentinel analyze --baseline golden` (default to latest golden)
- Warn on config hash mismatch
- Acceptance: baseline can be set/listed without DB edits

3) Minimal plugin system
- `mvp/parsers/<source>.py`
- `mvp/metrics/<metric>.py` (or YAML rules)
- `mvp/config/pipeline.yaml` to select parser + metrics
- Acceptance: new source/metric is a new file + config entry

4) Single-command user flow
- `sentinel analyze <path> --source pba_excel --baseline golden`
- One command runs ingest -> validate -> reduce -> compare -> report -> register
- Acceptance: full report directory is produced in one step

5) Painless install path
- Support `pipx install .` or a simple `make install` workflow
- Acceptance: a new engineer installs in under 10 minutes

### Optional for adoption beyond a single machine

- CI integration for automated runs (e.g., Jenkins/Git hooks)
- Shared registry and artifact retention policy for multi-user use
- Security and compliance layers for DoD/prime deployment

### Minimum Addendum (if you do only five things)

1. Source data contract (`--source` + schema + mapping)
2. Baseline tagging (`baseline set/list`)
3. Single-command analyze flow
4. Plugin layout (parsers + metrics as modules)
5. Easy install path (`pipx` or packaged binary)

### Revised MVP Acceptance Criteria (tight and realistic)

- `sentinel analyze <file> --source pba_excel --baseline golden` produces a report folder in under 2 minutes for typical logs
- It clearly reports: PASS, PASS-with-drift, FAIL (data/validation)
- A new engineer can install, run sample data, and understand the report in under 30 minutes
