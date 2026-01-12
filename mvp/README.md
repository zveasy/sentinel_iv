# Software-Only MVP

This folder contains the minimal artifacts to prove the core thesis:
- Ingest existing lab outputs (Excel/CSV/logs)
- Reduce raw data into repeatable health metrics
- Compare runs to a baseline and flag drift even when PASS

Quick start:
- Review acceptance criteria in `mvp/acceptance-criteria.md`
- Use the folder layout in `mvp/folder-structure.md`
- See the CLI spec in `mvp/cli.md`
- Start with the data schema in `mvp/schema/run-diff.json`
- Run the demo walkthrough in `mvp/demo/two-run-demo.sh`
- Install dependencies in `mvp/INSTALL.md`
- Run tests in `mvp/tests/README.md`
- Browse run registry with `python mvp/registry_cli.py list`
- Use the single-command flow with `./sentinel analyze <file> --source basic_csv --baseline golden`
- Define source schemas in `mvp/schemas/` and pipeline entries in `mvp/config/pipeline.json`
- Tag baselines with `./sentinel baseline set <run-id> --tag golden`
- Example header row lives in `mvp/schemas/hypothetical_lab_header.csv` with schema `mvp/schemas/hypothetical_lab.json`
- Example files: `mvp/runs/baseline/hypothetical-baseline.csv` and `mvp/runs/current/hypothetical-current.csv`
- PBA Excel schema: `mvp/schemas/pba_excel.json` with thresholds in `mvp/config/pba_excel_thresholds.yaml`
