# Operator Trust Layer — Confidence and Accuracy

**Purpose:** Give operators a clear answer to “Why should I trust this?” via confidence scores, historical accuracy tracking, and false positive / false negative metrics.

**References:** Reports (confidence, baseline_confidence), `docs/DECISION_AUTHORITY.md`, `hb/feedback.py`, `schemas/hb_event.json`.

---

## 1. What operators need

- **Confidence scores everywhere** — Every decision and report should expose confidence (and baseline_confidence) so operators know how strong the evidence is.
- **Historical accuracy** — “HB has been right X% of the time” (e.g. 97%).
- **False positive / false negative metrics** — Track when HB flagged something that was later deemed benign (FP) or missed something that was real (FN).

---

## 2. What’s implemented today

### 2.1 Confidence in reports and decisions

- **Reports:** `drift_report.json` and HTML include `baseline_confidence`, `baseline_match_level`, and per-metric attribution with confidence-like fields (e.g. from sample count). The engine also produces an overall confidence from baseline quality and compare.
- **Actions:** The action engine returns `confidence`, `baseline_confidence`, and `action_allowed` for each proposed or executed action (see `docs/DECISION_AUTHORITY.md`). These can be shown in UI and included in HB_EVENT payloads.
- **Streaming / runtime:** Decision snapshots can carry confidence and config_ref for audit.

### 2.2 Feedback loop (local)

- **Feedback Hub:** Operators can mark reports as “Correct”, “Too Sensitive”, or “Missed Severity” via the local feedback UI (`hb feedback serve`). Feedback is stored locally at `$HB_HOME/feedback/feedback_log.jsonl`.
- **Export:** `hb feedback export --output summary.json --mode summary` (or `raw`) to get a summary or full log. This is the **source of truth for FP/FN** once you define: e.g. “Too Sensitive” = potential false positive, “Missed Severity” = potential false negative.

### 2.3 What’s not yet implemented

- **Aggregate accuracy metrics:** No built-in “97% accuracy” number yet. You can compute it from feedback export: e.g. (Correct count) / (Correct + Too Sensitive + Missed Severity), or define accuracy per severity.
- **Persistent accuracy store:** Feedback is file-based (JSONL). For a formal “historical accuracy” dashboard, you could: (1) periodically export feedback and load into a DB or analytics store, or (2) add a small table (e.g. `accuracy_snapshots`: date, total_decisions, correct, false_positive, false_negative) and a job that aggregates from feedback_log.

---

## 3. Schema for accuracy tracking (optional)

To support “HB has been right 97% of the time” and FP/FN metrics, you can add:

### 3.1 Feedback event (already in use)

Feedback log entries today look like:

- `report_id`, `verdict` (Correct / Too Sensitive / Missed Severity), `note`, `timestamp`, etc.

### 3.2 Aggregation schema (for downstream or future HB feature)

```json
{
  "period": "2025-02",
  "total_labeled": 100,
  "correct": 95,
  "too_sensitive": 3,
  "missed_severity": 2,
  "accuracy_pct": 95.0,
  "false_positive_estimate": 3,
  "false_negative_estimate": 2
}
```

- **accuracy_pct** = correct / total_labeled (when total_labeled &gt; 0).
- **false_positive_estimate** = count of “Too Sensitive” (operator said HB over-flagged).
- **false_negative_estimate** = count of “Missed Severity” (operator said HB under-flagged).

This can be produced by a script that reads `feedback_log.jsonl` and outputs a monthly or rolling summary.

### 3.3 Display in UI

- In the report UI and operator dashboard: show **confidence** and **baseline_confidence** for the current decision.
- Add a “Trust” or “Accuracy” panel: “Based on N labeled reports: X% correct, Y potential false positives, Z potential false negatives.” Data source: feedback export or accuracy_snapshots.

---

## 4. Recommendations

1. **Use confidence everywhere** — Ensure every DRIFT_EVENT and ACTION_REQUEST includes `confidence`, `baseline_confidence`, and `action_allowed` (already in schema and action engine).
2. **Promote feedback** — Encourage operators to label reports (Correct / Too Sensitive / Missed Severity) so you can compute accuracy and FP/FN.
3. **Add an accuracy summary job** — Script or cron that reads feedback export, computes period accuracy and FP/FN counts, and writes to a small report or DB for dashboard.
4. **Document in runbook** — How to interpret confidence; how to export feedback and compute “HB has been right X% of the time” for briefings.

---

## 5. References

- **Decision authority:** `docs/DECISION_AUTHORITY.md`
- **HB_EVENT:** `schemas/hb_event.json`
- **Feedback:** `hb/feedback.py`; `bin/hb feedback serve`, `bin/hb feedback export`
- **Reports:** `drift_report.json` fields `baseline_confidence`, `baseline_match_level`, investigation_hints
