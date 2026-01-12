# Production Ready: Internal Lab MVP (Single Machine)

Target: A single-machine CLI workflow used by engineers in a lab. No formal compliance requirements.

Score: 100 / 100

Scope:
- Local CLI analysis with CSV/Excel/log ingestion.
- HTML report output and JSON diff artifacts.
- Lightweight config and thresholds management.

Checklist to reach 100 (implemented):
- Data ingestion: CSV, Excel, and log formats with basic parsing.
- Validation: schema checks with clear error messages and exit codes.
- Metrics config: threshold config via `mvp/config/thresholds.yaml`.
- Storage: local run registry at `mvp/registry/runs.db`.
- Artifacts: deterministic run IDs and report directories.
- Reporting: HTML report with summaries and drift highlights.
- Testing: parser and comparison tests in `mvp/tests/`.
- Packaging: pinned dependencies in `mvp/requirements.txt`.
- Documentation: quickstart references in `mvp/README.md`.

Deliverables:
- CLI package with `analyze` command.
- `mvp/registry/runs.db` (SQLite) with run metadata and artifacts.
- Deterministic run ID stored in `mvp/reports/<run-id>/`.
- `mvp/reports/<run-id>/run-report.html`, `run-diff.json`, `run-summary.txt`.
- `mvp/tests/` with parser/compare tests + golden report snapshot.
- `mvp/requirements.txt` + install instructions.
- Sample data + demo script for two-run drift story.

## Beyond 100 (Implemented Enhancements)

These steps are not required for the internal-lab target, but improve robustness and usability:
- Config versioning: report footer includes config hash and thresholds.
- Unit normalization: optional unit parsing with conversion via `unit_map`.
- Metric templates: named metric sets via `mvp/config/metric-templates.yaml`.
- Trend view: HTML summary via `python mvp/registry_cli.py trend`.
- Registry tooling: list/show commands via `python mvp/registry_cli.py`.
- Log verbosity: `--verbose` and `--quiet` flags.
- Error taxonomy: standardized exit codes for parse/validation/config/registry.

## Internal Lab Usability Addendum

Even for a single-machine MVP, pilots often fail without these must-haves:

Required to avoid pilot failure (implemented):
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

Optional for adoption beyond a single machine:
- CI integration (Jenkins/Git hooks)
- Shared registry and retention policy
- Security/compliance layers for DoD/prime deployment
