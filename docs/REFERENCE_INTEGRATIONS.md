# Reference Integrations — Lab Harness, Telemetry Bus, Prime-Like System

**Purpose:** Document reference integrations so production can prove: emit events → HB runtime consumes → decision → action request → ack → evidence pack, end-to-end.

**References:** `sdk/README.md`, `sdk/hb_event_client.py`, `schemas/hb_event.json`, `tools/e2e_embedding_test.py`.

---

## 1. Lab harness (Jenkins / Python)

- **Emit:** Use `sdk/hb_event_client.py emit --type DRIFT_EVENT --system-id <id> --status FAIL` to produce one HB_EVENT JSON line. Redirect to a file (e.g. `telemetry.jsonl`) for file_replay.
- **Or:** Generate metrics CSV + run_meta and call `hb run --source pba_excel <csv> --run-meta <meta>` from the harness (same contract as “events” for file-based flow).
- **Consume:** HB daemon with `source: file_replay` and `path: <telemetry.jsonl>`, or run `hb run` per job.
- **Decision → action → ack:** HB writes to action_ledger; harness (or WaveOS stub) calls `hb actions ack <action_id>` or posts ACTION_ACK to your webhook.
- **Evidence pack:** `hb export evidence-pack --case <run_id>` after the run.
- **E2E script:** `python tools/e2e_embedding_test.py --out-dir /tmp/hb_e2e --keep` runs the full chain (baseline + current run → decision → ack → evidence pack) and can be invoked from Jenkins.

---

## 2. Telemetry bus (Kafka / NATS / ZeroMQ)

- **Emit:** `sdk/hb_event_client.py emit --sink kafka --broker <broker> --topic hb/events` (requires `kafka-python`). C/C++: use your Kafka producer and serialize HB_EVENT to JSON (see `sdk/hb_event.h`).
- **Consume:** HB daemon with ingest source `kafka` (when available), or a bridge process that reads from Kafka and writes to file_replay path for HB.
- **Topic contract:** Publish HB_EVENT (DRIFT_EVENT, HEALTH_EVENT, ACTION_REQUEST) to `hb/events` (or configurable topic). HB subscribes to the same topic for ingest if using Kafka source.
- **NATS/ZeroMQ:** Same JSON payload; use NATS/ZeroMQ client in Python or C++ to publish. HB may need a small adapter that subscribes and forwards to HB (e.g. to file or to HB’s Kafka ingest if you add NATS bridge to Kafka).

---

## 3. Prime-like system (simulated flight software / hardware bench)

- **Simulated flight software:** Run a loop that produces telemetry (e.g. from a model or replay file), publishes to MQTT/Kafka in HB_EVENT shape (or metrics topic), and optionally subscribes for ACTION_REQUEST and sends ACTION_ACK.
- **Hardware bench:** Bench controller writes metrics (or raw telemetry) to a shared path or MQTT/Kafka; HB daemon on a co-located node ingests and publishes DRIFT_EVENT/ACTION_REQUEST; bench receives and logs or executes (e.g. degrade mode) and sends ACK.
- **Contract:** Same as above: HB_EVENT schema (`schemas/hb_event.json`), topic or file format, and ack via `hb actions ack` or WaveOS callback.

---

## 4. Definition of Done (E2E)

- [ ] A test rig can **emit** events (SDK client or CSV run).
- [ ] HB **runtime/daemon** consumes them (file_replay, MQTT, or Kafka).
- [ ] HB produces a **decision** (PASS / PASS_WITH_DRIFT / FAIL) and optional **action request** (in action_ledger).
- [ ] **Ack** is recorded (via `hb actions ack` or WaveOS ACTION_ACK).
- [ ] **Evidence pack** is exported for the run.
- **Run:** `python tools/e2e_embedding_test.py` (file-based path); for bus-based path, point daemon config to your broker/topic and run daemon + SDK emitter in parallel.
