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

Operator Quickstart (Local Web UI):
```
# Install Harmony Bridge locally (single command, no data leaves your machine)
pip install -r hb/requirements.txt -r hb/requirements-dev.txt

chmod +x bin/hb
bin/hb ui
```
Then open `http://127.0.0.1:8890/` and follow the on‑screen steps.

## Harmony Bridge Hybrid Eval Kit (HB-HEK-0.3)

Hybrid = CLI + local UI, one codepath. This is a local-only “website experience” shipped as a zip for evals.

What you ship:
- CLI for power users + CI
- Local Web UI for “let me try this in 2 minutes”
- Same core engine underneath (single compare API)

Folder layout (what the customer receives):
```
harmony-bridge-hybrid-kit-v0.3/
├── VERSION
├── README.md
├── QUICKSTART.md
├── LICENSE_EVAL.txt
├── bin/
│   ├── hb               # CLI entry
│   └── hb-ui            # starts local web UI (or hb ui)
├── app/
│   ├── server.py        # local web server (FastAPI/Flask)
│   ├── templates/       # UI HTML (or static build)
│   └── static/          # css/js
├── hb_core/
│   ├── ingest/
│   ├── schema/
│   ├── compare/
│   ├── scoring/
│   └── report/
├── config/
│   └── thresholds.yaml
├── examples/
│   ├── baseline/
│   ├── run_ok/
│   └── run_drift/
└── output/
    └── (empty)
```

User experience:
- CLI flow:
```
./bin/hb compare --baseline ./examples/baseline --run ./examples/run_ok --out ./output
open ./output/drift_report.html
```
- Local “website” flow:
```
./bin/hb ui
# opens http://127.0.0.1:8765
```

UI: Compare page (minimal but strong)
- Baseline: file/folder picker
- Run: file/folder picker
- Format: CSV / JSON autodetected
- Schema: Auto / Upload schema.yaml
- Output directory: default `./output/<timestamp>/`
- Button: Run Compare
- Result: status pill (PASS / YELLOW / FAIL) + “Open Report”

Optional: History page
- Recent runs list
- Open report
- Download `summary.json`

Single core API (CLI + UI call this):
```
result = hb_core.compare.run_compare(
    baseline_path=...,
    run_path=...,
    out_dir=...,
    schema_mode="auto" | "file",
    schema_path=...,
    thresholds_path=...
)
```

Local-only web UI posture (verbatim for README/QUICKSTART):
```
## Local-Only Web UI

The Harmony Bridge UI runs on your machine at:
http://127.0.0.1:8765

- The server binds to localhost only (not accessible externally).
- No data is uploaded anywhere.
- No telemetry or analytics are included.
- All artifacts are written to your selected output directory.
```

Packaging roadmap:
- Phase 1 (ship now): Python-based kit, `./bin/hb ui` starts local server, deps via `pip install -r requirements.txt`.
- Phase 2 (better UX): PyInstaller builds `hb` and `hb-ui` binaries (no Python needed).

Developer Setup:
```
python -m venv .venv
source .venv/bin/activate
pip install -r hb/requirements.txt -r hb/requirements-dev.txt
```

CLI Quickstart:
```
chmod +x bin/hb
bin/hb ingest --source pba_excel samples/cases/no_drift_pass/current_source.csv --run-meta samples/cases/no_drift_pass/current_run_meta.json --out runs/no_drift_pass_current
bin/hb analyze --run runs/no_drift_pass_current
```

Commands:
```
bin/hb ingest --source pba_excel <path-to-file> --run-meta <run_meta.json> --out runs/<run_id>/
bin/hb analyze --run runs/<run_id>/ --baseline-policy baseline_policy.yaml
bin/hb run --source pba_excel <path-to-file> --run-meta <run_meta.json>
bin/hb ui
bin/hb baseline set <run_id> --tag golden
bin/hb baseline request <run_id> --tag golden --requested-by "name"
bin/hb baseline approve <run_id> --tag golden --approved-by "name"
bin/hb baseline approvals
bin/hb baseline requests
bin/hb baseline list
bin/hb analyze --run runs/<run_id>/ --pdf
bin/hb analyze --run runs/<run_id>/ --redaction-policy redaction_policy.yaml
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
- Reports include baseline reason, match level, and top drift drivers for explainability.
- Optional PDF export uses `wkhtmltopdf` if installed (`drift_report.pdf`).
- If `wkhtmltopdf` is not available, a pure-Python fallback uses `fpdf2`.
- Each report folder includes `artifact_manifest.json` and `audit_log.jsonl`.
- Optional encryption/signing: use `--encrypt-key` and `--sign-key` with `bin/hb analyze` or `bin/hb run`.
- Optional redaction: use `--redaction-policy redaction_policy.yaml` to redact sensitive fields in report artifacts only.

Baseline governance:
- Enable approvals in `baseline_policy.yaml` under `governance.require_approval: true`.
- Request a baseline change with `bin/hb baseline request`.
- Approve with `bin/hb baseline approve --approved-by "<name>"`.

Streaming examples:
```
bin/hb ingest --source pba_excel samples/cases/no_drift_pass/current_source.csv --run-meta samples/cases/no_drift_pass/current_run_meta.json --out runs/no_drift_pass_current --stream
bin/hb run --source pba_excel samples/cases/no_drift_pass/current_source.csv --run-meta samples/cases/no_drift_pass/current_run_meta.json --stream
```

Quick demo (drift in ~30 seconds):
```
./tools/demo.sh
```
Runs baseline then current from `samples/cases/single_metric_drift`, prints report paths and "what to do next," and opens the drift report in your browser. Use `./tools/demo.sh --no-open` to skip opening the browser. The report includes **investigation hints** and a **What to do next** section that pinpoints the top issue and suggested actions.

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

Demo checklist:
1) Generate synthetic runs:
```
python tools/make_synthetic_runs.py --baseline-count 3 --drift-count 3 --out samples/synthetic
```
2) Run baseline + drift demo:
```
chmod +x tools/run_synthetic_demo.sh
tools/run_synthetic_demo.sh
```
3) Open a drift report:
```
open mvp/reports/<run_id>/drift_report.html
```
4) Confirm drift status and top metrics:
```
jq -r '.status, .baseline_run_id, (.top_drifts[]?.metric // empty)' mvp/reports/<run_id>/drift_report.json
```

Security/Compliance helpers:
```
bin/hb analyze --run runs/<run_id>/ --sign-key keys/signing.key
bin/hb analyze --run runs/<run_id>/ --encrypt-key keys/encryption.key
bin/hb verify --report-dir mvp/reports/<run_id> --sign-key keys/signing.key
python tools/generate_sbom.py --out SBOM.md
```
Audit integrity + rotation:
```
python tools/audit_integrity_check.py --reports-dir mvp/reports
python tools/audit_rotate.py --reports-dir mvp/reports --archive-dir logs/audit --max-bytes 5242880
```

SQLCipher (option 2) for encrypted runs.db:
```
chmod +x tools/sqlcipher_encrypt_db.sh
chmod +x tools/sqlcipher_decrypt_db.sh
tools/sqlcipher_encrypt_db.sh runs.db runs_encrypted.db "my-secret-key"
tools/sqlcipher_decrypt_db.sh runs_encrypted.db runs.db "my-secret-key"
```

SQLCipher wrapper commands:
```
bin/hb db encrypt --input runs.db --output runs_encrypted.db --key "my-secret-key"
bin/hb db decrypt --input runs_encrypted.db --output runs.db --key "my-secret-key"
```

Notes:
- If the output database exists, the scripts move it to a timestamped `.bak` before writing.

Multi-user lab guidance:
- Set shared paths via environment variables:
  - `HB_DB_PATH=/shared/hb/runs.db`
  - `HB_REPORTS_DIR=/shared/hb/reports`
  - `HB_METRIC_REGISTRY=/shared/hb/metric_registry.yaml`
  - `HB_BASELINE_POLICY=/shared/hb/baseline_policy.yaml`
- Prune old runs with retention policy:
```
python tools/retention_prune.py --policy retention_policy.yaml --db runs.db
```
- Backup the registry periodically:
```
chmod +x tools/backup_registry.sh
tools/backup_registry.sh runs.db backups
```

Distribution drift (optional):
- If a metric's `tags` contains JSON with `"samples": [...]`, Harmony Bridge can run a KS statistic.
- Configure with `distribution_drift` in `metric_registry.yaml`.
- Toggle distribution drift with `distribution_drift_enabled` in `baseline_policy.yaml`.
Example Tags JSON in CSV:
```
Metric,Baseline,Current,Delta,Threshold,Unit,Tags,Status
avg_latency_ms,10,10,,,ms,"{""samples"":[9,10,10,11,9,10,10,11]}",
```

Investigation hints and "What to do next":
- Every drift report (HTML and JSON) includes a **What to do next** paragraph and per-metric **investigation hints**: pinpoint (one-sentence cause), suggested actions (e.g. re-baseline, check latency), and root-cause category (e.g. Drift threshold exceeded, Invariant violated).
- The CLI prints a short "what to do next" line after each analyze so you see the summary in the terminal without opening the report.
- See `Questions/q_and_a.md` for how drift, coverage, and verdicts are computed.

Context-aware baseline fields:
- `run_meta.json` can include `operating_mode`, `scenario_id`, `sensor_config_id`, `input_data_version`, and `environment_fingerprint`.
- When present, baseline selection prefers runs with matching context and reports match level in the output.

CMAPSS FD001 regression (local dataset):
```
export CMAPSS_ROOT=/Users/zakariyaveasy/Downloads/CMAPSSData
python tests/real_data/cmapss_fd001/run_regression.py
```
CMAPSS FD002–FD004 regression (local dataset):
```
export CMAPSS_ROOT=/Users/zakariyaveasy/Downloads/CMAPSSData
python tests/real_data/cmapss_fd002/run_regression.py
python tests/real_data/cmapss_fd003/run_regression.py
python tests/real_data/cmapss_fd004/run_regression.py
```
NASA HTTP TSV regression (local dataset):
```
export NASA_HTTP_TSV_ROOT=/Users/zakariyaveasy/Downloads/nasa_http_tsv
python tests/real_data/nasa_http_tsv/run_regression.py
```
Expected: early window PASS; mid/late windows PASS_WITH_DRIFT.
SMAP/MSL regression (local dataset):
```
export SMAP_MSL_ROOT=/Users/zakariyaveasy/Downloads/labeled_anomalies
python tests/real_data/smap_msl/run_regression.py
```
Expected: baseline windows PASS; anomaly windows PASS_WITH_DRIFT.
SMAP/MSL manifest regeneration:
```
python tools/smap_msl_make_manifest.py --root /Users/zakariyaveasy/Downloads/labeled_anomalies --output tests/real_data/smap_msl/manifest.yaml
```
CMAPSS auto-tune helper (dry-run by default):
```
export CMAPSS_ROOT=/Users/zakariyaveasy/Downloads/CMAPSSData
python tools/cmapss_autotune.py --variant fd003 --engine 1 --window 150 200 --p 0.70
python tools/cmapss_autotune.py --variant fd003 --engine 1 --window 150 200 --p 0.70 --write
```
CI guard for CMAPSS configs:
```
python tools/ci/check_cmapss_config_usage.py --config configs/cmapss_fd003_thresholds.yaml --allow-regression
```

Performance tools:
```
python tools/benchmark_streaming.py --file samples/large/large_pba.xlsx --runs 3
```

CI benchmark threshold (optional):
```
HB_BENCH_FILE=samples/large/large_pba.xlsx HB_BENCH_MAX_S=2.0 pytest -q
```

Docker (Windows-compatible):
```
docker build -t harmony-bridge .
docker run --rm -it -v "${PWD}:/app" harmony-bridge python hb/cli.py --help
```

Docker quickstart (full run):
```
docker run --rm -it -v "${PWD}:/app" harmony-bridge \
  python hb/cli.py run --source pba_excel samples/cases/no_drift_pass/current_source.csv \
  --run-meta samples/cases/no_drift_pass/current_run_meta.json
```

docker-compose (Windows-friendly):
```
docker compose run --rm harmony-bridge python hb/cli.py --help
docker compose run --rm harmony-bridge \
  python hb/cli.py run --source pba_excel samples/cases/no_drift_pass/current_source.csv \
  --run-meta samples/cases/no_drift_pass/current_run_meta.json
```

DoD lab offline + secure install:
- `docs/OFFLINE_INSTALL.md`
- `docs/SECURE_INSTALL.md`
- `docs/RUNBOOK.md`

Tests:
```
pytest -q
```

Feedback loop (local only):
- Start the local feedback server:
```
bin/hb feedback serve
```
- Open the Feedback Hub (local UI): `http://127.0.0.1:8765/`
- This runs a Local Feedback Service (only on your machine). It never accepts external connections.
- Use the report UI buttons (Correct / Too Sensitive / Missed Severity) and optional note/time.
- Opt-in toggle is required before sending.
- Info icon tooltips explain privacy and decision basis details.
- Feedback is stored locally at `$HB_HOME/feedback/feedback_log.jsonl` (default `~/.hb/feedback/feedback_log.jsonl`).
- Export a summary or raw records:
```
bin/hb feedback export --output feedback_summary.json --mode summary
bin/hb feedback export --output feedback_raw.json --mode raw
```

Feedback loop quick test (no data leaves the machine):
1) Start server:
```
bin/hb feedback serve
```
2) Generate a drift report (example):
```
bin/hb run --source pba_excel samples/cases/single_metric_drift/baseline_source.csv \
  --run-meta samples/cases/single_metric_drift/baseline_run_meta.json \
  --db /tmp/hb_feedback_test.db --reports /tmp/hb_feedback_reports
bin/hb run --source pba_excel samples/cases/single_metric_drift/current_source.csv \
  --run-meta samples/cases/single_metric_drift/current_run_meta.json \
  --db /tmp/hb_feedback_test.db --reports /tmp/hb_feedback_reports
```
3) Open the report:
```
open /tmp/hb_feedback_reports/single_metric_drift_current/drift_report.html
```
4) In the report UI:
   - Enable feedback sending.
   - Click Correct / Too Sensitive / Missed Severity.
   - Add an optional note and time-to-resolution.
5) Verify receipt:
```
curl http://127.0.0.1:8765/count
```
6) Download a summary from the Feedback Hub or:
```
curl http://127.0.0.1:8765/export?mode=summary
```

Local Web UI (localhost only):
- Start the UI (binds to `127.0.0.1` only):
```
bin/hb ui
```
- Open `http://127.0.0.1:8890/`
- Choose a workspace (default `~/.harmony_bridge`).
- Install Baseline, then Analyze/Compare with the current run.
- The report auto-opens and is linked in the UI.
- Export Support Bundle (report + logs + manifest, no raw inputs) from the UI after a run.
- Use the Watch Folder panel to start/stop periodic checks without a terminal.
- Interval presets: Weekly / Monthly / Yearly.

Watch folder (periodic drift checks, local only):
```
bin/hb watch --dir /path/to/incoming --source pba_excel --pattern "*.csv" --interval 604800
```
Options:
- `--run-meta /path/to/run_meta.json` for a shared run meta.
- `--run-meta-dir /path/to/run_meta/` to match `file.csv` with `file.json`.
- `--workspace /path/to/workspace` (default `~/.harmony_bridge`).
- `--open-report` to auto-open each report.
- `--once` to process current files and exit.

Sample cases quick-run (baseline + current for every case, then open reports):
```
chmod +x tools/run_sample_cases.sh
tools/run_sample_cases.sh
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
