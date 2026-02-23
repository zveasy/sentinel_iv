# Action Policy Tiers and Governance

**Purpose:** Tiered action policy and break-glass override so no critical action happens without meeting policy + approvals + audit trail.

**References:** `config/actions_policy.yaml`, `hb/actions/engine.py`, `docs/DECISION_AUTHORITY.md`, `docs/BREAK_GLASS_OVERRIDE.md`.

---

## 1. Action tiers

| Tier | Allowed actions | Use case |
|------|------------------|----------|
| **Tier 0** | Observe only (no actions emitted) | Audit / read-only mode. |
| **Tier 1** | Notify + evidence (notify, evidence pack export) | Alerts and evidence only. |
| **Tier 2** | Request degrade / failover | Soft mitigation. |
| **Tier 3** | Request abort / shutdown (requires 2-man rule + persistence) | Critical; safety gate + decision_authority + optional approval. |

**Implementation:** In action policy YAML, rules can specify `tier: 0|1|2|3`. When `effective_tier` is set (e.g. to 2), the engine only executes actions with tier ≤ effective_tier. Tier 3 actions already require two independent conditions and (optionally) time_persistence_cycles and baseline approval workflow.

---

## 2. Break-glass override

- **Time-limited:** Override expires (e.g. 24h); `--override-expires-in 24h`.
- **Audited:** Audit log records `break_glass_override` with reason, operator_id, expires_at.
- **Reason code required:** `--override-reason` mandatory when `--break-glass` is used.
- **RBAC:** When `HB_RBAC=1`, only approver (or admin) can use break-glass.

See `docs/BREAK_GLASS_OVERRIDE.md` and CLI `--break-glass`, `--override-reason`, `--override-operator-id`, `--override-expires-in`.

---

## 3. Who can approve baseline promotion

- **Governance:** `baseline_policy.yaml` → `governance.require_approval: true`.
- **Request:** `hb baseline request <run_id> --tag golden --requested-by "<name>"`.
- **Approve:** `hb baseline approve <run_id> --tag golden --approved-by "<name>" --reason "<reason>"`.
- **RBAC:** When `HB_RBAC=1`, only role `approver` or `admin` can run `baseline approve`; `viewer`/`operator` can request only.
- **Audit:** `baseline_approvals` and `baseline_requests` tables; custody and audit log.

---

## 4. Definition of done

- No critical action (shutdown/abort) without: safety gate (two conditions) + decision_authority (confidence, multi-signal) + optional fail_safe check.
- Break-glass is time-limited, audited, and reason code required; RBAC enforced when enabled.
- Baseline promotion requires request + approve when governance enabled; RBAC enforces who can approve.
