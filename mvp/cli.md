# CLI Specification (MVP)

Command:

```
python mvp/analyze.py --run <file> --baseline <file> --config <thresholds.yaml> --out <dir>
```

Required arguments:
- `--run`: current run file (CSV/Excel/logs)
- `--baseline`: baseline run file

Optional arguments:
- `--config`: thresholds config (default: `mvp/config/thresholds.yaml`)
- `--out`: output directory (default: `mvp/reports/<run-id>`)
- `--format`: report format (`html` or `xlsx`), default: `html`
- `--run-id`: override run ID used for storage
- `--registry`: SQLite registry path (default: `mvp/registry/runs.db`)
- `--templates-config`: metric templates config (default: `mvp/config/metric-templates.yaml`)
- `--template`: template name to filter metrics
- `--verbose`: verbose logging
- `--quiet`: suppress non-error output

Outputs:
- `run-summary.txt` (PASS, PASS-with-drift, FAIL)
- `run-report.html` (or `.xlsx`)
- `run-diff.json` (baseline comparison)

Supported input formats:
- CSV: `metric,value`
- Excel: `.xlsx` with `metric` and `value` columns (requires `openpyxl`)
- Logs: `.txt` or `.log` with `metric,value`, `metric: value`, or `metric=value`

Exit codes:
- `2` parse error
- `3` validation error
- `4` config error
- `5` registry error

Registry tooling:

```
python mvp/registry_cli.py list --limit 20
python mvp/registry_cli.py show <run-id>
python mvp/registry_cli.py trend --out mvp/reports/trend.html
```

Single-command flow:

```
./sentinel analyze <file> --source basic_csv --baseline golden
./sentinel baseline set <run-id> --tag golden
./sentinel baseline list
```

Notes:
- If `--baseline` is omitted, `golden` is used by default.
- For PBA Excel, use `--source pba_excel --config mvp/config/pba_excel_thresholds.yaml`.

Source pipelines:
- Source definitions live in `mvp/config/pipeline.json`
- Schemas live in `mvp/schemas/`
- Baseline tags live in `mvp/registry/runs.db`
