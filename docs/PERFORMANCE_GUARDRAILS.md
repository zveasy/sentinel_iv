# Performance guardrails and resource limits

## Documented limits

- **Max file size (ingest):** Single-file ingest (CSV, Excel, JSONL) is not hard-limited; very large files (e.g. >500 MB) may require significant memory. Use streaming where available: set `HB_STREAM_INGEST=1` or `--stream` for supported adapters (e.g. CSV, PBA Excel) to process in chunks.
- **Memory:** Non-streaming ingest loads the source file into memory. For large inputs, use streaming or split the file.
- **Run registry (SQLite):** No built-in row limit; periodic pruning is recommended for long-lived deployments (see `tools/retention_prune.py`).
- **Daemon:** Config options `max_report_dir_mb` and `max_audit_log_mb` cap disk usage; reports are pruned when over limit. Buffer for telemetry is in-memory (last `window_sec` of events).
- **Reports:** Each report is a fixed-size HTML/JSON; report count is bounded by daemon disk caps or manual retention.

## Tuning

- **Streaming:** Prefer `hb ingest --stream` and `HB_STREAM_INGEST=1` for large CSV/Excel to reduce peak memory.
- **Database:** SQLite with WAL is used; for very high write throughput consider moving to a dedicated DB (future).
- **Daemon window:** Reduce `window_sec` in `config/daemon.yaml` if the event buffer grows too large.

## Tuning for large datasets

- **Split inputs:** For very large CSV/Excel (e.g. >100 MB), consider splitting by time or scenario and running multiple ingest+analyze jobs.
- **Streaming:** Always use `--stream` or `HB_STREAM_INGEST=1` for CSV/PBA when available to bound memory.
- **Registry:** Run `python tools/retention_prune.py` periodically to cap run count; keep baseline runs needed for comparison.
- **Daemon:** For high event rates, increase `interval_sec` so each cycle aggregates more data; keep `window_sec` moderate (e.g. 300–900) to limit buffer size.
- **Metric registry:** Limit the number of metrics in `metric_registry.yaml` for programs that produce many columns; alias only the columns you need for drift/asserts.

## CI

Performance benchmarks and failure criteria can be added to CI (e.g. `tools/perf_check.py`, `tools/benchmark_compare.py`). The optional "Perf check" step in `.github/workflows/ci.yml` runs when `perf_limits.yaml` and a perf.json are present. See the 2–3 week closeout in `mvp/production-readiness.md` for Week 3 tasks.
