# Performance Envelope — Published Envelope for HB

**Purpose:** A published performance envelope: “HB supports X events/sec, Y metrics, Z windows with p99 < N ms.” Use for sizing and SLOs.

**References:** `docs/REALTIME_GUARANTEES.md`, `tools/load_gen.py`, `tests/test_streaming_benchmark.py`.

---

## 1. Envelope statement (template)

Fill in after running load and soak tests for your build and hardware:

| Parameter | Value | Notes |
|-----------|--------|--------|
| **Events/sec sustained** | X (e.g. 10,000) | No unbounded memory; use `tools/load_gen.py --profile 10k`. |
| **Metrics per run** | Y (e.g. 100) | Metric registry size. |
| **Sliding windows** | Z (e.g. 1000 buckets) | `max_buckets` in runtime config. |
| **p99 decision latency** | N ms (e.g. 50) | From streaming benchmark or latency recorder. |
| **p99.9 decision latency** | N9 ms | Worst-case characterization (run soak + percentile). |
| **Daemon cycle** | &lt; interval_sec | Cycle completes before next tick (e.g. 30–60 s). |
| **Batch analyze** | &lt; 2 min | For &lt; 10k rows, &lt; 100 metrics. |

**Example published envelope:**

- **HB supports 10k events/sec, 100 metrics, 1000 windows with p99 &lt; 50 ms** (on reference hardware: 4 vCPU, 8 GB RAM). p99.9 &lt; 200 ms. Daemon cycle &lt; 30 s for 30 s interval. Batch analyze &lt; 2 min for 50k rows.

---

## 2. How to produce the envelope

1. **Load generator:** `python tools/load_gen.py --profile 10k --duration-sec 60 --out /tmp/load.jsonl` (or `--profile 50k`, `100k`).
2. **Soak test:** Run daemon or streaming evaluator consuming `load.jsonl` (file_replay) for duration; observe memory and latency (Prometheus or latency recorder export).
3. **Benchmark:** `pytest tests/test_streaming_benchmark.py`; optional `HB_STREAMING_BENCH_EVENTS`, `HB_STREAMING_BENCH_MAX_S`.
4. **Percentiles:** From latency snapshot (p50, p95, p99, p99.9); document in this file or release notes.
5. **Backpressure:** When overloaded, policy is drop/aggregate/degrade (see `docs/REALTIME_GUARANTEES.md` §4); fail-safe mode disables dangerous actions when timing cannot be met (see action policy `fail_safe_on_timing`).

---

## 3. Backpressure policy (deterministic)

| Condition | Behavior | Config |
|-----------|----------|--------|
| **Overload** | Drop oldest events (time-bound eviction) or evict oldest buckets | `window_sec`, `max_buckets` |
| **Circuit open** | Skip daemon cycle; no actions emitted | `circuit_breaker` in daemon.yaml |
| **Timing SLO missed** | Enter fail-safe: no shutdown/abort actions; notify only | `fail_safe_on_timing: true` in actions_policy |

---

## 4. Fail-safe mode (no dangerous actions when timing cannot be met)

In `config/actions_policy.yaml`:

```yaml
# When true, critical actions (shutdown, abort) are never executed; only notify/degrade allowed.
# Use when latency SLO is missed or circuit breaker is open.
fail_safe_on_timing: false   # set true in ops when under stress
```

Implementation: action engine checks `context.get("fail_safe")` or `context.get("timing_slo_met")`; when fail_safe is true, only Tier 0–1 actions (observe, notify) are allowed. See `docs/ACTION_TIERS.md` (or decision authority).
