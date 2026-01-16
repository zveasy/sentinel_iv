# Harmony Bridge Run Contract

Harmony Bridge consumes run artifacts and normalizes them into a stable contract:

Required files per run:
- `run_meta.json`
- `metrics.csv`

Optional:
- `events.jsonl`

## run_meta.json

```json
{
  "run_id": "...",
  "program": "nasams",
  "subsystem": "fire_control",
  "test_name": "nightly_regression_suite",
  "environment": "hil|simics|lab",
  "build": {"git_sha":"...", "build_id":"..."},
  "timestamps": {"start_utc":"...", "end_utc":"..."},
  "toolchain": {"source_system":"pba_excel"}
}
```

## metrics.csv

CSV schema:

```
metric,value,unit,tags
avg_latency_ms,12.4,ms,
reset_count,0,,critical
```

Rules:
- `metric` is canonical name (from `metric_registry.yaml`)
- `value` is numeric
- `unit` optional; used for conversion
- `tags` optional string

## events.jsonl (optional)

Line-delimited JSON events from the source system. Not required for MVP.
