# Memory Caps and Safe Degradation

For long-lived daemon or streaming runs, cap memory and degrade gracefully when limits are exceeded.

## Configurable caps

- **Daemon:** Use `max_report_dir_mb` and `max_audit_log_mb` in `config/daemon.yaml` to limit disk; the daemon prunes oldest report dirs when over. No in-process metric count cap is applied today; telemetry buffer is trimmed by `window_sec` (time window).
- **Streaming:** `SlidingWindowAggregator` accepts optional `max_buckets`. When set, oldest window buckets are evicted so the number of buckets never exceeds the cap. Use in runtime config: `max_buckets: 1000` in `config/runtime.yaml` (see `hb runtime --config`). This bounds memory for long-lived streaming.

## Implementation notes

- **Current:** Daemon buffer is `[e for e in buffer if e.get("_ts", 0) >= cutoff]` with `cutoff = now - window_sec`, so memory is bounded by event rate × window_sec. Large windows or high throughput can still grow memory.
- **Recommendation:** Set `window_sec` and `interval_sec` to match your telemetry rate; use `max_report_dir_mb` to avoid unbounded disk. For strict memory bounds, add a config key (e.g. `max_buffer_events`) and trim to oldest N when exceeded (drop or aggregate).

## References

- `hb/daemon.py`: buffer pruning by time; `prune_reports()` for disk.
- `hb/streaming/windows.py`: sliding window aggregator (incremental); `max_buckets` for max-size eviction; `prune_before(watermark)` for time-based eviction.
