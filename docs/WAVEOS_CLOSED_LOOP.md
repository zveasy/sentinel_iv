# Full Closed-Loop: HB ↔ WaveOS and Control Hierarchy

**Purpose:** Define the autonomous loop between Harmony Bridge and WaveOS: bidirectional state sync, policy ownership, and who decides (HB vs WaveOS vs Operator).

**References:** `docs/WAVEOS_CONTRACT.md`, `hb/adapters/waveos.py`, `schemas/waveos_events.json`, `schemas/hb_event.json`.

---

## 1. Bidirectional state sync

### 1.1 HB → WaveOS (already in contract)

| Event | When | Content |
|-------|------|--------|
| **HEALTH_EVENT** | Periodic or on health change | Status, primary issue, run_id, drift_metrics. |
| **DRIFT_EVENT** | Drift or FAIL detected | status, severity, recommended_action, confidence, baseline_confidence, action_allowed. |
| **ACTION_REQUEST** | HB proposes an action | action_type, action_id, params, confidence, action_allowed. |

WaveOS consumes these (e.g. via webhook or message bus) and may apply mode changes, policy, or actuator commands.

### 1.2 WaveOS → HB (already in contract)

| Event | When | Content |
|-------|------|--------|
| **ACTION_ACK** | WaveOS completed or rejected an action | action_id, status (ok / nack), message. |
| **MODE_CHANGED** | Operational mode was changed | from_mode, to_mode, reason. |
| **POLICY_APPLIED** | Policy update was applied | policy_id, version. |

HB should consume these to:

- **Update action ledger:** Mark action as acked or failed (action_ledger ack_at, ack_payload).
- **Sync operational mode:** Update HB’s view of system mode so baseline selection and thresholds use the correct mode (see `hb/modes.py`).
- **Audit:** Log POLICY_APPLIED with policy version and timestamp.

### 1.3 Closing the loop

1. HB detects drift/FAIL and sends DRIFT_EVENT + optional ACTION_REQUEST.
2. WaveOS receives, optionally applies action (degrade, failover, etc.), and sends ACTION_ACK.
3. If WaveOS changes mode, it sends MODE_CHANGED; HB updates mode and may re-select baseline or re-evaluate.
4. HB records ACTION_ACK in the action ledger and in audit; next cycle uses updated mode.

**Gap to close in implementation:** Ensure HB has a defined way to **receive** WaveOS events (webhook endpoint, or poll from a queue). Today the WaveOS adapter can publish; the consumer side (HB listening for ACTION_ACK, MODE_CHANGED, POLICY_APPLIED) may be stub or callback-only. Document the exact endpoint or topic and payload in runbook.

---

## 2. Policy ownership and control hierarchy

**Who decides?**

| Level | Decides | Example |
|-------|--------|--------|
| **Operator** | Override, approve baselines, break-glass | Operator approves baseline change; operator uses break-glass to force PASS. |
| **WaveOS** | Mode, policy application, actuator commands | WaveOS decides when to apply a policy or change mode; it may reject an ACTION_REQUEST. |
| **HB** | Drift detection, recommended action, confidence, action_allowed | HB decides PASS/FAIL, recommends DEGRADE/SHUTDOWN; it does not directly command hardware—it sends ACTION_REQUEST. |

### 2.1 Control hierarchy (who wins)

1. **Operator override** — Highest. Break-glass and manual approvals override HB and WaveOS for that decision or baseline.
2. **WaveOS** — Can reject or delay an ACTION_REQUEST; can change mode independently (e.g. maintenance). WaveOS is the **executor** of actions on the system.
3. **HB** — **Advisor and detector.** HB recommends; WaveOS (and optionally operator) decides whether to execute. HB’s `action_allowed` is a gate: when false, HB is saying “do not auto-execute this”; when true, WaveOS may still refuse.

### 2.2 Policy ownership

| Policy | Owned by | Notes |
|--------|----------|--------|
| Metric thresholds, invariants, baseline policy | HB (config) | HB loads from YAML; can be overridden by operator or WaveOS via config push (rate-limited). |
| Action policy (when to notify, degrade, shutdown) | HB (config) | Same; WaveOS does not edit HB action policy directly unless via an explicit “policy update” API. |
| Operational mode transitions | WaveOS (or operator) | Mode changes are reported to HB via MODE_CHANGED; HB uses mode for baseline selection. |
| Execution of actions (e.g. actual shutdown) | WaveOS | WaveOS executes; HB only requests. |

### 2.3 Documenting in runbook

- **RUNBOOK:** Add a “Control hierarchy” section: Operator &gt; WaveOS &gt; HB for execution; HB is the source of drift and recommendation; WaveOS is the source of mode and action execution.
- **Integration:** Document how WaveOS sends ACTION_ACK and MODE_CHANGED to HB (URL, topic, payload) and how HB stores them (ledger, audit, mode state).

---

## 3. Summary

- **Bidirectional sync:** HB → WaveOS (HEALTH, DRIFT, ACTION_REQUEST); WaveOS → HB (ACTION_ACK, MODE_CHANGED, POLICY_APPLIED). Implement or document the WaveOS→HB ingestion path.
- **Control hierarchy:** Operator overrides &gt; WaveOS execution &gt; HB recommendation. HB never directly controls hardware; it sets `action_allowed` and recommends.
- **Policy ownership:** HB owns threshold and action policy config; WaveOS owns mode and execution. Document in runbook and in this doc.
