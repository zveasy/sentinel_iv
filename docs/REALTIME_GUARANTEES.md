# Real-Time Guarantees and Behavior Under Stress

**Purpose:** Document what DoD can expect from Harmony Bridge under load: worst-case latency, load testing, backpressure, and degradation strategy. HB is not a hard real-time OS; this doc defines soft real-time targets and measurable behavior.

**References:** `docs/MEMORY_CAPS.md`, `hb/streaming/`, `hb/daemon.py`, `docs/FAILOVER_HA.md`.

---

## 1. Execution model

- **Streaming evaluator:** Event-time processing, watermarks, sliding windows; incremental aggregation to bound work per event.
- **Daemon:** Periodic cycle (e.g. every N seconds); ingests from configured sources, runs compare, emits alerts and optional actions.
- **Batch (run/analyze):** Single-shot ingest + compare; latency depends on file size and metric count.

HB does **not** provide hard real-time (e.g. guaranteed 50ms under all loads on a general-purpose OS). It provides **soft real-time** targets and documented behavior when limits are exceeded.

---

## 2. Latency targets and measurement

### 2.1 Target bounds (operational)

| Scenario | Target (p95) | Notes |
|----------|--------------|--------|
| Streaming decision (per window) | &lt; 50 ms | From last event in window to decision emitted; depends on window size and metric count. |
| Daemon cycle (ingest → report) | &lt; cycle_interval_sec | Typically 30–60 s; cycle should complete before next tick. |
| Single run (analyze) | &lt; 2 min | Typical &lt; 10k rows, &lt; 100 metrics; scale with size. |

### 2.2 Worst-case latency (not average)

- **Streaming:** Worst case is dominated by: (1) window flush (all buckets evaluated), (2) number of metrics × number of buckets. Use `max_buckets` and window length to cap work.
- **Benchmarks:** `tests/test_streaming_benchmark.py` and `tools/benchmark_streaming.py` measure throughput and latency. Run with `HB_STREAMING_BENCH_EVENTS` and `HB_STREAMING_BENCH_MAX_S` to stress.
- **Documented worst case:** For a given config (max_buckets, metrics count, window size), worst-case decision time is proportional to O(metrics × buckets); document your config’s expected upper bound in ops runbook.

### 2.3 Latency in reports and metrics

- **Decision latency:** `hb/streaming/latency.py` records p50/p95 decision time; Prometheus exposes these when `hb health serve` is used with the streaming evaluator.
- **SLO:** Define in ops: e.g. “p95 decision latency &lt; 50 ms” and alert when exceeded; see observability in `docs/PRODUCTION_HB_DOD_ROADMAP.md` §5.2.

---

## 3. Load testing at scale

### 3.1 Target load

- **10k+ metrics/sec:** Ingest and streaming evaluator should sustain 10k events/sec without unbounded memory growth. Use `max_buckets` and window eviction; benchmark in CI when enabled (`HB_STREAMING_BENCH_EVENTS`).
- **Large batch:** `samples/large/` and `tools/make_large_xlsx.py` (e.g. 50k rows); `hb ingest` + `hb analyze` should complete within documented time (e.g. &lt; 2 min for 50k rows).

### 3.2 How to run load tests

- **Streaming:** `pytest tests/test_streaming_benchmark.py` (smoke, throughput, max_buckets). Optional env: `HB_STREAMING_BENCH_EVENTS`, `HB_STREAMING_BENCH_MAX_S`.
- **Batch:** `python tools/benchmark_streaming.py --file samples/large/large_pba.xlsx --runs 3`.
- **CI:** Optional threshold: `HB_BENCH_FILE=... HB_BENCH_MAX_S=2.0 pytest -q`.

### 3.3 Documenting results

- Record in runbook or release notes: “Validated at X k events/sec; p95 decision latency Y ms with config Z.”
- For DoD: include in V&V package (see `docs/VV_TEST_PLAN.md`) as performance qualification.

---

## 4. Backpressure and degradation strategy

### 4.1 Backpressure

- **Streaming:** If the upstream (e.g. Kafka) supports backpressure, slow consumption when HB is overloaded. HB does not currently push backpressure to the ingest socket; it drops or buffers according to config (e.g. window time-bound eviction).
- **Daemon:** Circuit breaker: after N consecutive failures, daemon opens circuit and skips cycles until cooldown; config in `config/daemon.yaml` (`circuit_breaker`). Prevents runaway when downstream (DB, report dir) is failing.
- **Memory:** Bounded by `max_buckets` (streaming) and `window_sec` (daemon buffer). When exceeded, oldest data is evicted; see `docs/MEMORY_CAPS.md`.

### 4.2 Degradation strategy (documented)

| Condition | Behavior | Operator action |
|-----------|----------|-----------------|
| Cycle overrun | Daemon completes current cycle; next cycle may be delayed. | Increase `interval_sec` or reduce metric count/window. |
| Circuit breaker open | Daemon skips ingest/analyze until cooldown. | Fix DB/storage; restart daemon if needed. |
| Memory pressure | Evict oldest buckets (streaming) or trim buffer (daemon). | Reduce `max_buckets` or `window_sec`; scale horizontally. |
| Disk full | Report/audit write fails; daemon may fail cycle. | Increase disk or prune via `max_report_dir_mb` / retention. |

### 4.3 Safe defaults

- **Configurable caps:** `max_report_dir_mb`, `max_audit_log_mb`, `max_buckets`, `window_sec` so that operators can set hard limits and get predictable degradation instead of OOM or unbounded disk.

---

## 5. Summary for DoD

- **Worst-case latency:** Documented per config; measured via benchmarks and optional CI. Target: p95 decision &lt; 50 ms for streaming with defined config.
- **Load testing:** 10k+ events/sec sustained with bounded memory; use streaming benchmark and large-file batch benchmark; document results in V&V.
- **Backpressure:** Circuit breaker and time/size-based eviction; no unbounded queues in core path.
- **Degradation:** Documented strategy (overrun, circuit open, memory, disk) and safe defaults so behavior under stress is predictable and auditable.
