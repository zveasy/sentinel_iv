# Decision Authority — Confidence-Based Action Gating

**Purpose:** Document how HB gates actions on confidence and multi-signal validation so the system is safe enough for real control: don’t trigger critical actions from a single metric or low confidence.

**References:** `hb/actions/engine.py`, `hb/actions/policy.py`, `config/actions_policy.yaml`, `docs/OPERATOR_TRUST.md`.

---

## 1. Problem

HB suggests and can trigger actions (notify, degrade, failover, abort, shutdown). For real system control, DoD expects:

- **Confidence-based gating:** Don’t allow hard actions unless decision confidence and baseline confidence are above thresholds.
- **Multi-signal validation:** Don’t trigger shutdown/abort from one metric; require multiple metrics (and optionally time persistence) to agree.

---

## 2. Implementation

### 2.1 Policy: `decision_authority`

In `config/actions_policy.yaml` (or your policy file):

```yaml
decision_authority:
  min_confidence: 0.85
  min_baseline_confidence: 0.70
  min_metrics_for_critical: 2
  time_persistence_cycles: 2
```

| Key | Meaning | Default |
|-----|---------|--------|
| **min_confidence** | Decision confidence (0–1) must be ≥ this to allow any action. | 0 (off) |
| **min_baseline_confidence** | Baseline confidence (0–1) must be ≥ this to allow any action. | 0 (off) |
| **min_metrics_for_critical** | For shutdown/abort, at least this many metrics must be flagged. | 2 |
| **time_persistence_cycles** | For critical actions, condition must have persisted this many cycles (if available). | 0 (off) |

### 2.2 Context passed to the action engine

When calling `ActionEngine.execute()` or `propose_actions()`, pass **context** with:

| Key | Type | Description |
|-----|------|-------------|
| **confidence** | float 0–1 | Decision confidence (e.g. from compare or baseline quality). |
| **baseline_confidence** | float 0–1 | Baseline lineage/quality confidence. |
| **flagged_metric_count** | int | Number of metrics in fail or drift set. |
| **persistence_cycles** | int | Number of consecutive cycles this condition has held (optional). |

Example (from analyze/daemon integration):

```python
context = {
    "confidence": 0.94,
    "baseline_confidence": 0.88,
    "flagged_metric_count": 2,
    "persistence_cycles": 2,
}
results = engine.execute(status="FAIL", context=context, independent_conditions=[...])
```

### 2.3 Returned shape: `decision`, `confidence`, `baseline_confidence`, `action_allowed`

Every result from `execute()` and `propose_actions()` includes:

- **decision** — Status (e.g. FAIL).
- **confidence** — From context.
- **baseline_confidence** — From context.
- **action_allowed** — `True` only if safety gate and decision_authority both pass.

Example:

```json
{
  "decision": "DEGRADE",
  "confidence": 0.94,
  "baseline_confidence": 0.88,
  "action_allowed": true
}
```

When blocked:

- **reason:** `"confidence_below_min"`, `"baseline_confidence_below_min"`, `"multi_signal_not_met"`, `"time_persistence_not_met"`, or `"safety_gate_not_passed"`.

### 2.4 Safety gate (unchanged)

Critical actions (shutdown, abort) still require **two independent conditions** when `safety_gate.require_two_conditions` is true (e.g. status FAIL and baseline_confidence < 0.3). Decision authority adds an extra layer: even when the safety gate passes, `action_allowed` can be false if confidence or multi-signal bars are not met.

---

## 3. HB_EVENT and downstream systems

When emitting **HB_EVENT** (e.g. DRIFT_EVENT or ACTION_REQUEST), include `confidence`, `baseline_confidence`, and `action_allowed` so downstream systems (WaveOS, test bench, flight software) can:

- Display confidence to operators.
- Refuse to execute if `action_allowed` is false.
- Log for audit and operator trust (see `docs/OPERATOR_TRUST.md`).

Schema: `schemas/hb_event.json`.
