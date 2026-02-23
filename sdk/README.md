# HB SDK & Reference Integrations

**Purpose:** Enable real system embedding by providing a reference client and **compiled C library** that emit **HB_EVENT** and consume decisions/acks. Use from lab harness (Jenkins/Python), telemetry bus (Kafka/NATS/ZeroMQ), or prime-like systems.

**Definition of Done:** A test rig can emit events → HB runtime consumes → decision → action request → ack → evidence pack, end-to-end.

---

## Contents

| Item | Description |
|------|-------------|
| **`libhb_event.a` / `libhb_event.so`** | Compiled C library: `hb_event_create`, `hb_event_serialize`, `hb_event_parse`, getters/setters. Build with `make` in this directory. |
| **`hb_event.c`** | C implementation (no external deps). |
| **`hb_event.h`** | C header: opaque struct, serialize/parse, create/free, set/get. |
| **`hb_event_client.py`** | Python reference client: build/send HB_EVENT; optional Kafka publish. |
| **`examples/cpp/send_event.cpp`** | C++ example: send one DRIFT_EVENT (link with libhb_event.a). |
| **`examples/cpp/receive_ack.cpp`** | C++ example: parse ACTION_ACK from stdin. |
| **Reference integrations** | See `docs/REFERENCE_INTEGRATIONS.md`: lab harness, Kafka/NATS/ZeroMQ, prime-like system. |

---

## Quick start (Python)

```bash
# From repo root
export PYTHONPATH="${PWD}"
python sdk/hb_event_client.py --help
# Emit one DRIFT_EVENT to stdout (for pipe to HB or file_replay)
python sdk/hb_event_client.py emit --type DRIFT_EVENT --system-id asset-001 --status FAIL --confidence 0.9
# Emit to Kafka (requires broker)
python sdk/hb_event_client.py emit --type DRIFT_EVENT --system-id asset-001 --status FAIL --sink kafka --broker localhost:9092 --topic hb/events
```

---

## Building the C library

```bash
cd sdk
make              # builds libhb_event.a and libhb_event.so
make clean
```

Link your C/C++ program with `-L/path/to/sdk -lhb_event` (or use the full path to `libhb_event.a` for static link).

## Building the C++ examples

**From repo root** (recommended):

```bash
make -C sdk                    # build library first
make -C examples/cpp          # build send_event and receive_ack
./examples/cpp/send_event
echo '{"type":"ACTION_ACK","action_id":"x","action_allowed":true}' | ./examples/cpp/receive_ack
```

**From `examples/cpp`** (after building the SDK from repo root):

```bash
cd examples/cpp
make
./send_event
./receive_ack   # then paste JSON line and Enter
```

Do **not** run the example compile from inside `sdk/`—paths are relative to the repo root.

## C++ / C contract

See **`hb_event.h`**. Implementations should:

1. **Emit:** Serialize HB_EVENT to JSON (or fixed buffer) and send to configured transport (file, socket, Kafka producer, etc.).
2. **Consume (optional):** Read ACTION_REQUEST or DECISION_SNAPSHOT from HB; send ACTION_ACK back (e.g. HTTP or bus).

A full C++ SDK (e.g. linking to a telemetry library) is a separate build; this repo provides the **contract** and Python reference.
