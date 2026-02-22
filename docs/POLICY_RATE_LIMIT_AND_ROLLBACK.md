# Policy Rate Limit and Rollback

For WaveOS and operator workflows: rate-limited policy updates, staged rollout, and rollback (roadmap 6.2.2).

## Rate limiter

- **Module:** `hb/policy_rate_limit.py`. `PolicyRateLimiter(config)` with `PolicyRateLimitConfig(max_updates_per_minute=10, min_interval_sec=6)`.
- **Usage:** Before applying a baseline or config change (e.g. `hb baseline set`, or a policy API), call `limiter.allow()`. If `False`, defer the update or return 429; otherwise proceed. Use `time_until_next_sec()` to tell the client when to retry.
- **Integration:** In an API or daemon that applies policy updates, instantiate one limiter per process and call `allow()` before each update. Configure via config YAML (e.g. `policy_updates.max_per_minute`, `policy_updates.min_interval_sec`) and pass into `PolicyRateLimitConfig`.

## Version and staged rollout

- **Versioning:** Policy and metric registry are file-based; version them via Git or your deployment pipeline. Evidence and run metadata store config hashes (`registry_hash`, `policy_hash`) so each run is tied to a specific version.
- **Staged rollout:** Deploy a new baseline or policy to a canary (e.g. one daemon or one program) first. Use the rate limiter to cap how often you switch. Compare outcomes (drift, actions) before rolling out to all nodes.
- **Rollback:** To roll back:
  1. **Baseline:** Point baseline policy back to a previous tag or run_id (e.g. `hb baseline set <previous_run_id> --tag golden`), or restore `baseline_policy.yaml` from Git and redeploy.
  2. **Config:** Restore the previous `metric_registry.yaml` / `baseline_policy.yaml` from version control and restart the daemon or reload config.
  3. **Evidence:** Each run records which baseline and registry hashes were used; use `replay` or reports to verify behavior under the previous version.

## References

- `hb/policy_rate_limit.py` — `PolicyRateLimiter`, `PolicyRateLimitConfig`
- `docs/POLICY_PROVENANCE.md` — who changed policy, config hashes in evidence
- `docs/WAVEOS_CONTRACT.md` — WaveOS policy/action contract
