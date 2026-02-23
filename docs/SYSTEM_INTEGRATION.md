# Hard System Integration — Embedding HB into Real Systems

**Purpose:** Close the gap between “HB as integrable platform” and “HB as system embedded into real systems” (flight software, telemetry buses, embedded systems, test benches). This doc defines the formal interface, integration options, and deterministic execution expectations.

**References:** `schemas/hb_event.json`, `docs/WAVEOS_CONTRACT.md`, `docs/REALTIME_GUARANTEES.md`.

---

## 1. Formal interface: HB_EVENT contract

HB emits and consumes events that conform to the **HB_EVENT** schema. Use this contract for:

- Telemetry bus integration (publish/subscribe)
- C++ bindings or SDK (same JSON/bytes on the wire)
- Test bench and HIL adapters
- WaveOS and other control-plane integrations

### Event types (HB → system)

| Type | When | Key fields |
|------|------|------------|
| **DRIFT_EVENT** | Drift or failure detected | `type`, `timestamp`, `system_id`, `severity`, `recommended_action`, `status`, `confidence`, `baseline_confidence`, `action_allowed`, `drift_metrics`, `report_path` |
| **HEALTH_EVENT** | Periodic or on-change health summary | `status`, `primary_issue`, `run_id` |
| **ACTION_REQUEST** | Request for system to perform an action | `action_type`, `action_id`, `confidence`, `action_allowed`, `payload` |
| **DECISION_SNAPSHOT** | Deterministic decision record (replay/audit) | `decision`, `confidence`, `baseline_confidence`, `action_allowed`, `config_ref`, `input_slice_ref` |

### Minimum payload (every HB_EVENT)

```json
{
  "type": "DRIFT_EVENT",
  "timestamp": "2025-02-22T12:00:00Z",
  "system_id": "asset-001",
  "severity": "high",
  "recommended_action": "DEGRADE",
  "status": "FAIL",
  "confidence": 0.94,
  "baseline_confidence": 0.88,
  "action_allowed": true
}
```

- **Schema:** `schemas/hb_event.json` (JSON Schema draft-07).
- **Serialization:** JSON over MQTT/Kafka/syslog or bytes for embedded; same logical fields.

---

## 2. Flight software / real system hooks

### What exists today

- **Python API:** `hb` CLI and Python modules (engine, streaming, actions, ingest). Any host that can run Python can call `run`, `analyze`, `runtime`, `actions execute`.
- **Adapters:** MQTT, Kafka, syslog, file-replay ingest; WaveOS adapter for events.
- **Event shape:** Reports and WaveOS adapter emit health/drift/action shapes; these are aligned with `hb_event.json` so that a thin adapter can map to HB_EVENT.

### What’s missing (integration layer)

| Gap | Deliverable |
|-----|-------------|
| **C++ bindings / SDK** | Formal C/C++ API (or FFI) that: (1) receives telemetry bytes/structs, (2) calls into HB core (e.g. via subprocess or shared library), (3) returns decision + HB_EVENT-shaped struct. Design: `docs/SYSTEM_INTEGRATION.md` § C++ SDK (this section); implementation is a separate project (e.g. pybind11 or ctypes wrapper around Python, or native reimplement of compare/runtime). |
| **Direct telemetry bus integration** | HB already has MQTT/Kafka/syslog ingest. “Direct” means: documented topic names, QoS, and HB_EVENT as the published payload so that flight software or test benches publish once and HB subscribes. Use `config/daemon.yaml` and ingest sources; document topic/schema in runbook. |
| **Embedded / test bench** | Same as above: feed telemetry via MQTT/Kafka/file-replay; HB runs on a co-located or gateway node and publishes HB_EVENT back to a bus that the bench or embedded side consumes. No HB runtime on bare-metal embedded today; gateway pattern is the intended integration. |

### C++ / SDK design (contract)

- **Input:** Telemetry buffer (e.g. struct or JSON) + optional run_id/system_id.
- **Output:** HB_EVENT (DRIFT_EVENT or DECISION_SNAPSHOT) with `decision`, `confidence`, `baseline_confidence`, `action_allowed`.
- **Invocation:** (A) Subprocess: C++ spawns `hb runtime` or `hb run` with stdin/config, reads stdout/JSON result. (B) Shared library: Python extension or native module that links to HB core; same in/out contract.
- **Determinism:** Same input + same config → same `decision` and `action_allowed`; see `docs/REALTIME_GUARANTEES.md` and `docs/DETERMINISM_AND_REPLAY.md`.

---

## 3. Deterministic execution guarantees

DoD expects predictable behavior under load and clear bounds.

- **Decision determinism:** Same input slice + same config/registry → same decision. Implemented: `hb replay`, determinism tests, decision snapshots with config_ref.
- **Latency and real-time:** Not hard real-time in the OS sense. Soft real-time and worst-case behavior are documented in `docs/REALTIME_GUARANTEES.md` (e.g. target max latency, load testing, backpressure).
- **50ms decision bound:** That is a product/operational target; configuration and measurement approach are in REALTIME_GUARANTEES. Meeting it depends on metric count, window size, and hardware.

---

## 4. Implementation checklist (embedding HB)

1. **Adopt HB_EVENT** — All external event payloads (to WaveOS, to bus, to test bench) conform to `schemas/hb_event.json`.
2. **Document topic and transport** — For MQTT/Kafka/syslog: topic names, message format (HB_EVENT), and who publishes/subscribes (runbook or PROGRAM_ONBOARDING).
3. **Confidence and action_allowed** — Every DRIFT_EVENT and ACTION_REQUEST includes `confidence`, `baseline_confidence`, and `action_allowed` so downstream systems can gate automation; see decision authority in code and `docs/OPERATOR_TRUST.md`.
4. **C++/SDK** — If required: implement wrapper (subprocess or shared lib) that preserves HB_EVENT contract and document in this doc.
5. **Determinism and replay** — Use `hb replay` and V&V package to prove same input → same decision; reference REALTIME_GUARANTEES for latency and load.

---

## 5. References

- **Event schema:** `schemas/hb_event.json`
- **WaveOS:** `docs/WAVEOS_CONTRACT.md`, `docs/WAVEOS_CLOSED_LOOP.md`
- **Real-time and latency:** `docs/REALTIME_GUARANTEES.md`
- **Determinism:** `docs/DETERMINISM_AND_REPLAY.md`
- **V&V:** `docs/VV_TEST_PLAN.md`, `docs/VV_ACCEPTANCE_CRITERIA.md`
