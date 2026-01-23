# Artifact Schema (v1.0)

The artifact contract is a system-agnostic input folder used by `hb plan run` (analyze-only mode) and adapters.

## Folder layout

```
artifact_dir/
├── run_meta.json
├── metrics.csv
├── signals.csv          # optional
├── events.jsonl         # optional
├── logs.jsonl|logs.txt  # optional
└── attachments/         # optional
```

## run_meta.json (required)

Required fields:
- `program`
- `subsystem`
- `test_name`
- `schema_version` (defaults to 1.0 if omitted)

Optional fields:
- `run_id`
- `toolchain.source_system`
- `timestamps.start_utc`, `timestamps.end_utc`

## metrics.csv (required)

Columns:
- `metric` (string)
- `value` (numeric)
- `unit` (optional)
- `tags` (optional)

## signals.csv (optional)

Required columns:
- `timestamp` or `ts`
Additional columns are treated as signals.

## events.jsonl (optional)

Each line is a JSON object with event metadata.

## Schema versioning + migration notes

Version bumps are additive unless noted:
- v1.0: initial contract with `run_meta.json` + `metrics.csv`.

If a breaking change is needed:
1) bump `schema_version` in `run_meta.json`
2) add a migration note here
3) keep a compatibility path where possible

## Adapter example: VxWorks logs

The VxWorks adapter can transform a raw log into an artifact directory by counting:
- ERROR lines
- WARN/WARNING lines
- RESET lines

This produces a `metrics.csv` with `error_count`, `warn_count`, and `reset_count`.
