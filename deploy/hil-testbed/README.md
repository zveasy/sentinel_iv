# HIL Testbed

Reference testbed: **broker → HB daemon → health endpoint**, with optional WaveOS stub.

## Layout

- **mosquitto**: MQTT broker (port 1883).
- **hb-daemon**: Sentinel HB daemon (file_replay or MQTT ingest; config via mount).
- **health**: Health server (`/ready`, `/live`, `/metrics`) on port 9090.
- **waveos-stub**: Placeholder for WaveOS (ACTION_ACK); extend to subscribe to HB topics.

## Usage

From repo root:

```bash
docker compose -f deploy/hil-testbed/docker-compose.yaml up --build
```

- Health: `curl http://localhost:9090/live` and `curl http://localhost:9090/metrics`.
- To use MQTT ingest, set in `config/daemon.yaml`: `source: mqtt`, `broker: tcp://mosquitto:1883`, and publish telemetry to the configured topic.

## Telemetry

For file_replay, mount a telemetry JSONL into the daemon container and set `path` in daemon config. For MQTT, use a separate publisher or the MQTT CLI to publish to `hb/metrics/#`.
