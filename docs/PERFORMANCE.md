# Performance Profiling

Perf data is emitted to `perf.json` in each report directory.

Check against limits:

```
python tools/perf_check.py --perf mvp/reports/<run_id>/perf.json --limits configs/perf_limits.yaml
```

Adjust limits in `configs/perf_limits.yaml` based on your lab hardware and data sizes.
