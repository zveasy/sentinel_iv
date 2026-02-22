# Failover and High Availability

## Active/standby deployment

Run two HB instances: one **active** (ingesting and deciding), one **standby** (ready to take over). Use a shared store for checkpoints and optional DB so the standby can resume from the last cycle.

### Checkpoint sync

- **Daemon checkpoint:** `output_dir/daemon_checkpoint.json` and `output_dir/checkpoint_history/checkpoints.jsonl` (see `max_checkpoint_history` in config).
- **Shared storage:** Mount the same NFS/EFS or object bucket path for `output_dir` and `db_path` on both nodes so the standby sees the same checkpoint and DB.
- **Takeover:** Stop the active daemon; start the standby with the same config. It will read the last checkpoint and continue from the next cycle. No application-level replication is required if storage is shared.

### Single-writer

Only one daemon should write to a given `output_dir` and `db_path` at a time. Use a lock (e.g. file lock or leader election) or orchestration (e.g. Kubernetes with one replica) to ensure a single active instance.

### Optional: checkpoint sync to standby

If you cannot share storage, periodically copy `daemon_checkpoint.json` and `checkpoint_history/` (and optionally `runs.db`) from active to standby. On failover, start the standby with the copied data. Recovery is from the last copied checkpoint; cycles between copy and failover are lost.

## Health and failover triggers

- Use **liveness** (`/live`) so the orchestrator restarts the pod/process if it hangs.
- Use **readiness** (`/ready`) so the load balancer stops sending traffic when DB or config is unavailable.
- For active/standby behind a single VIP, use external leader election (e.g. etcd, Consul) or your platform’s primitive (e.g. StatefulSet with one replica) rather than HB implementing it.

## References

- `hb health serve` exposes `/live`, `/ready`, `/metrics`.
- Checkpoint format: `daemon_checkpoint.json` (last_cycle_utc, last_status, last_report_dir); history in `checkpoint_history/checkpoints.jsonl`.
