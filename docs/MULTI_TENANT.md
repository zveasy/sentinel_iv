# Multi-Tenant / Program Partitioning

**Purpose:** One install supports multiple programs without data bleed; separate namespaces for baselines, runs, keys; per-program RBAC and retention.

**References:** `hb/registry.py` (program in runs, list_runs(program=)), `hb/rbac.py`, `hb/config.py` (program overrides).

---

## 1. Program partitions

- **Runs:** Every run has `program` (and subsystem, test_name). Use `hb runs list --program <name>` to scope.
- **Baselines:** Baseline tags are global; baseline selection can prefer same program (context-aware selection uses program from run_meta).
- **Registry:** `list_runs(conn, program=...)` filters by program; set `HB_PROGRAM` env to default scope for CLI.
- **Metric registry:** `metric_registry.yaml` can define `programs.<name>.metrics` overrides for per-program thresholds (see `hb/config.py` _apply_program_overrides).

---

## 2. Per-program RBAC (future)

- **Target:** Per-program roles (e.g. operator for program A cannot approve baselines for program B). Today RBAC is global; extend with program scope in permission checks.
- **Config:** Optional `rbac.program_roles: { "program_a": ["operator"], "program_b": ["viewer"] }` and check in baseline approve / evidence export.

---

## 3. Per-program retention and redaction

- **Retention:** `retention_policy.yaml` can include per-program rules (e.g. retain program A 90 days, program B 30 days). Implement in `tools/retention_prune.py` with program filter.
- **Redaction:** Use different `redaction_policy` or profiles per program when exporting evidence (e.g. `--redaction-profile program_a_export`).

---

## 4. Export/import between enclaves (air-gapped)

- **Export:** `hb export evidence-pack --case <id> --program <name>` (optional) to limit to one program’s data; redact and encrypt; write to transfer media.
- **Import:** In receiving enclave, no direct “import run” today; document workflow: transfer evidence pack and load into case management; HB in the other enclave runs independently with its own DB. (Full DB sync or import would be a separate feature.)

---

## 5. Definition of done

- One install can support multiple programs: runs and baselines scoped by program; list/filter by program; metric overrides per program.
- Per-program RBAC and retention are documented and partially implemented (program in runs, list_runs(program=), program overrides in registry); full per-program approve and retention filters are follow-on.
- Export for air-gap: evidence pack with optional program scope and redaction; import workflow documented.
