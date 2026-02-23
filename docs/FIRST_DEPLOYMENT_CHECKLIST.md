# First Real Deployment Checklist

**Purpose:** The only thing that truly matters for moving from “potential” to “proven” is **one real system** with live data, real alerts, real actions, and real evidence packs. This checklist helps you get there.

**References:** `docs/PILOT_2WEEK_SPRINT.md`, `docs/REPO_SUMMARY.md`, `deploy/`, `docs/RUNBOOK.md`.

---

## 1. Choose your first system

Pick **one** of:

- **Microgrid** — Best fit for many DoD energy/resilience use cases; clear telemetry (power, frequency, load).
- **Lab test system** — Existing HIL or bench with MQTT/Kafka/syslog or file export.
- **Simulated NASAMS-style telemetry** — Synthetic stream that mimics a real system for proof of concept.

Criteria: You can get **live or replayable data** and (for closed loop) a **consumer of actions** (even a stub that logs).

---

## 2. Pre-deployment

| # | Item | Done |
|---|------|------|
| 2.1 | Telemetry source identified (MQTT topic, Kafka topic, syslog, or file-replay path). | ☐ |
| 2.2 | Schema or mapping from raw telemetry to HB metrics (metric_registry, optional telemetry_schema). | ☐ |
| 2.3 | Baseline strategy: golden run or time-window baseline; baseline created and tagged. | ☐ |
| 2.4 | Action consumer: who receives ACTION_REQUEST / DRIFT_EVENT? (WaveOS stub, webhook, file sink.) | ☐ |
| 2.5 | One node or VM for HB (daemon + optional UI). Network access to telemetry and (if needed) to action consumer. | ☐ |
| 2.6 | Config files: daemon.yaml, metric_registry, baseline_policy, actions_policy (and decision_authority if using confidence gating). | ☐ |

---

## 3. Deployment day

| # | Item | Done |
|---|------|------|
| 3.1 | Install HB (pip or kit); create workspace; set HB_DB_PATH, HB_REPORTS_DIR, config paths. | ☐ |
| 3.2 | Run ingest once (or replay) to populate a baseline run; run `hb baseline set <run_id> --tag golden`. | ☐ |
| 3.3 | Start daemon: `hb daemon` (or systemd unit). Confirm one cycle completes: check report dir and DB. | ☐ |
| 3.4 | Trigger or wait for a **real drift** (e.g. inject fault, or use a known-bad run). Confirm status FAIL or PASS_WITH_DRIFT and report generated. | ☐ |
| 3.5 | Confirm **real alerts**: alert sink (stdout/file/webhook) receives an event. | ☐ |
| 3.6 | Confirm **real actions**: if action consumer is connected, ACTION_REQUEST is received and (if applicable) ACTION_ACK returned. | ☐ |
| 3.7 | Export **evidence pack** for one run: `hb export evidence-pack --case <id>` or from report dir; verify manifest and artifacts. | ☐ |
| 3.8 | Document: system name, date, telemetry source, baseline tag, one example run_id and report path. | ☐ |

---

## 4. Post–first deployment

| # | Item | Done |
|---|------|------|
| 4.1 | Run 24h (or one shift) without crash; circuit breaker and checkpoint behavior verified under load. | ☐ |
| 4.2 | Collect at least one “real alert” and one “real evidence pack” for a briefing or demo. | ☐ |
| 4.3 | Update RUNBOOK with system-specific steps (topics, config paths, contact). | ☐ |
| 4.4 | Optional: feedback loop — operators label a few reports (Correct / Too Sensitive / Missed Severity) and export for accuracy narrative. | ☐ |

---

## 5. Definition of “first deployment done”

- [ ] One real system (microgrid, lab bench, or simulated) is feeding HB.
- [ ] Live data (or replay) is being analyzed; baseline is set.
- [ ] At least one real drift/FAIL has been detected and reported.
- [ ] Real alerts have been emitted to a sink.
- [ ] Real actions have been requested (and optionally acked) by a consumer.
- [ ] At least one evidence pack has been exported and verified.
- [ ] Date and system name are recorded; one run_id and report path are kept as proof.

Until this exists, the product is still “potential.” After this, you have a reference deployment and a story for DoD and customers.
