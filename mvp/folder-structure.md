# Minimal Folder Structure

Use this layout for the software-only MVP:

```
sentinel_iv/
  mvp/
    README.md
    acceptance-criteria.md
    folder-structure.md
    cli.md
    schema/
      run-diff.json
    config/
      thresholds.yaml
      metric-templates.yaml
      pipeline.json
      pba_excel_thresholds.yaml
    schemas/
      basic_metrics.json
      pba_excel.json
      hypothetical_lab.json
      hypothetical_lab_header.csv
    parsers/
      csv_parser.py
      excel_parser.py
      log_parser.py
      table_csv_parser.py
    metrics/
      pass_through.py
    sentinel.py
    registry/
      runs.db
    demo/
      two-run-demo.sh
    runs/
      baseline/
        baseline-run.csv
      current/
        current-run.csv
    reports/
      <run-id>/
  sentinel
  Makefile
```

Notes:
- `runs/` holds input files only.
- `reports/` holds generated artifacts.
- `config/thresholds.yaml` defines drift thresholds.
