# Pilot Report Template — First Real Deployment

**Purpose:** Capture operational value and adoption for the “graduation” pilot: one lab data source, one streaming source, golden baseline workflow, nightly watch + weekly evidence exports; measure time saved, drift caught, reduction in NFF/time-to-triage.

**References:** `docs/FIRST_DEPLOYMENT_CHECKLIST.md`.

---

## 1. Pilot summary

| Field | Value |
|-------|--------|
| **Pilot name** | |
| **Site / lab** | |
| **Start date** | |
| **End date** | |
| **System(s) under test** | (e.g. microgrid, bench, simulated flight) |

---

## 2. Data sources

| Source | Type | Description |
|--------|------|-------------|
| **Primary (file)** | PBA Excel / CSV / other | e.g. nightly export from test harness |
| **Primary (streaming)** | MQTT / Kafka / other | e.g. live telemetry topic |
| **Baseline workflow** | Golden tag / rolling | How baseline was set and updated |

---

## 3. Operational workflow

- **Nightly watch:** (e.g. `hb watch --dir ... --interval 86400`) or cron-driven run.
- **Weekly evidence exports:** (e.g. `hb export evidence-pack` for FAIL runs or weekly summary).
- **Alerts:** Where alerts were sent (stdout, file, webhook) and who acted on them.

---

## 4. Metrics (measure value)

| Metric | Before pilot | After pilot | Notes |
|--------|----------------|-------------|--------|
| **Time to triage (avg)** | | | e.g. hours to identify cause of drift |
| **Drift caught that tests missed** | — | Count / examples | |
| **NFF reduction** | — | Count / % | No-Fault-Found investigations avoided or shortened |
| **Time saved (hrs/week)** | — | | Engineer time saved on manual analysis |
| **Adoption** | — | e.g. “3 engineers using HB for triage” | Non-authors using the system |

---

## 5. Adoption by non-authors

- **Who used HB:** Roles and number.
- **Feedback:** Correct / Too Sensitive / Missed Severity (from feedback log or survey).
- **Blockers or friction:** What would improve adoption.

---

## 6. Conclusion and recommendation

- **Operational value:** One-line summary (e.g. “HB caught N drift events that standard tests missed and reduced triage time by X%.”).
- **Recommendation:** Proceed to broader rollout / next phase (e.g. second lab, more programs).

---

## 7. Evidence and artifacts

- Attach or reference: sample evidence pack, redacted report, runbook updates, support bundle (if permitted).
- Sign-off: Pilot owner, date.
