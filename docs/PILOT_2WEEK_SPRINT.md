# 2-Week Sprint: “HB Runs 24h on a Laptop with Simulated Telemetry”

**North star:** Before buying hardware, HB must run nonstop, ingest live-like telemetry, build a baseline, detect drift, emit alerts + evidence pack, and survive restart.

**Definition of done for this milestone:**
- `hb daemon` runs nonstop
- Receives MQTT and/or syslog (or file-replay) telemetry
- Builds baseline automatically (or via `hb baseline create`)
- Detects drift on a schedule
- Emits alerts (e.g. stdout/file/webhook) + evidence pack on FAIL
- Survives process restart (checkpointing / resume)

---

## Sprint Overview

| Week | Focus | Outcomes |
|------|--------|----------|
| **Week 1** | Connectors + normalization + baseline lifecycle + daemon skeleton | `hb ingest --source mqtt\|syslog\|file-replay`, `hb normalize`, `hb baseline create`, `hb daemon` (polling loop) |
| **Week 2** | Streaming/continuous mode, alerting, evidence-pack automation, resilience, hardening | `hb daemon` with rolling windows, `hb alert`, `hb export evidence-pack`, durability + install hardening |

Fault injection and WaveOS integration are **out of scope** for this 2-week sprint; they are listed at the end as follow-on work.

---

## Week 1: Connectors, Normalization, Baseline Lifecycle, Daemon Skeleton

### 1) Real telemetry ingestion (connectors)

**Goal:** `hb ingest --source mqtt|syslog|file-replay` so HB can consume live or replayed telemetry.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **1.1** Add `ingest` source registry and adapter interface | `hb/ingest/__init__.py`, `hb/ingest/sources/base.py` | `BaseIngestSource` with `connect()`, `read()/stream()`, `close()`. Existing file-based ingest remains; new sources plug in. |
| **1.2** Syslog/journald adapter | `hb/ingest/sources/syslog.py` | Read from Unix socket `/dev/log` or file path; parse RFC 5424 / common formats; output structured `{timestamp, host, program, msg, fields}`. Optional: `journalctl -f` subprocess. |
| **1.3** MQTT adapter | `hb/ingest/sources/mqtt.py` | Use `paho-mqtt` or `aiomqtt`; subscribe to configurable topics; parse payload (JSON or key=value); map to metric name + value; optional `--broker`, `--topic`, `--qos`. Add `paho-mqtt` to `hb/requirements.txt`. |
| **1.4** File-replay adapter | `hb/ingest/sources/file_replay.py` | Read from a file (e.g. JSONL or CSV) line-by-line with optional speed limit (e.g. 1 line/sec) to simulate live feed. Reuse existing CSV/JSON parsing where possible. |
| **1.5** Wire sources into CLI | `hb/cli.py` | `hb ingest --source mqtt --broker tcp://localhost:1883 --topic telemetry/# --out ./live` (and similar for `syslog`, `file-replay`). Ingest writes to `--out` in the same artifact layout (e.g. `metrics.csv`, `run_meta.json`, optional `events.jsonl`). |

**Acceptance:** `hb ingest --source file-replay path/to/telemetry.jsonl --out ./out` and `hb ingest --source mqtt --broker tcp://localhost:1883 --topic hb/metrics --out ./out` (with a broker running) both produce artifact dirs that `hb analyze` can use.

---

### 2) Telemetry schema + normalization layer

**Goal:** A single place to map vendor-specific names → canonical names and units (ms vs s, kW vs W).

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **2.1** Telemetry schema / mapping file | `config/telemetry_schema.yaml` or extend `metric_registry.yaml` | YAML: `sources.mqtt.topic_map`, `sources.syslog.patterns`, and a `field_mapping` (vendor_name → canonical_metric, unit conversion). |
| **2.2** Normalize pipeline | `hb/normalize.py` | `normalize_telemetry(raw_events, schema) → list[dict]` with metric, value, unit, timestamp. Unit conversion (e.g. W→kW, ms→s) via schema. |
| **2.3** `hb normalize` command | `hb/cli.py` | `hb normalize --schema config/telemetry_schema.yaml --input ./raw_events.jsonl --output ./normalized_metrics.csv` (or write into artifact dir). |

**Acceptance:** Raw MQTT/syslog payloads with vendor-specific names and mixed units produce a normalized CSV/artifact that matches existing `metric_registry.yaml` canonical names so the rest of the pipeline is unchanged.

---

### 3) Baseline training + baseline management

**Goal:** Baselines are versioned, timestamped, and promotable; “train baseline for 24h/7d” is possible.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **3.1** Baseline “create” from time window | `hb/baseline.py` or extend registry | `hb baseline create --window 24h` (or `7d`): aggregate metrics from runs in the last 24h/7d (or from a specified run set), compute e.g. median/mean per metric, write a baseline artifact + metadata (version, timestamp, source_run_ids). |
| **3.2** Baseline versioning in DB | `hb/registry.py` | Table or columns: `baseline_version`, `created_at`, `source_runs`, `signature` (optional). `hb baseline list` shows versions. |
| **3.3** `hb baseline promote` | `hb/cli.py` | `hb baseline promote --version v2 --tag golden`: set tag to a specific baseline version so future analyzes use it. |
| **3.4** Optional: sign baseline artifact | Reuse existing signing in `hb/security.py` | Baseline artifact (e.g. `baseline_metrics.csv` + `baseline_meta.json`) can be signed; `baseline_meta.json` includes version, timestamp, run_ids. |

**Acceptance:** `hb baseline create --window 24h` produces a new baseline version; `hb baseline list` shows it; `hb baseline promote --version <id> --tag golden` switches the golden baseline; next `hb analyze` uses that baseline.

---

### 4) Daemon skeleton (streaming / continuous mode)

**Goal:** `hb daemon` runs continuously, runs periodic drift checks, and supports rolling windows.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **4.1** Daemon entrypoint and config | `hb/daemon.py`, `config/daemon.yaml` (optional) | `hb daemon --config config/daemon.yaml`: loop that (a) ingests from configured source (mqtt/syslog/file-replay), (b) buffers telemetry in memory or a small DB, (c) every N minutes runs a “window” compare (e.g. last 5 min vs baseline). |
| **4.2** Config schema for daemon | `config/daemon.yaml` | `source: mqtt|syslog|file-replay`, connection params, `interval_sec`, `window_5m`, `window_1h`, `baseline_tag`, `output_dir`, `db_path`. |
| **4.3** Rolling windows | `hb/daemon.py` or `hb/engine.py` | For each check: current window = last 5 min (or 1 hr) of normalized metrics; baseline = current golden baseline or last 24h aggregate. Call existing `compare_metrics` + report. |
| **4.4** systemd unit (template) | `deploy/hb-daemon.service` | Template unit file: `ExecStart=.../bin/hb daemon --config ...`, `Restart=always`, `User=hb` (non-root). Document in README. |

**Acceptance:** `hb daemon` runs without crashing; it reads from file-replay or MQTT (if broker present), and every N minutes writes a report to `output_dir` (or logs “no drift” / “drift”). No alerting yet in Week 1.

---

## Week 2: Alerting, Evidence Packs, Resilience, Hardening

### 5) Alerting + response outputs

**Goal:** When drift/FAIL is detected, HB emits structured events to configurable sinks (no manual HTML opening).

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **5.1** Alert event schema | `schemas/alert_event.json` or inline in code | JSON: `{ "ts", "severity": "WARN|FAIL|CRITICAL", "status", "run_id", "primary_issue", "report_path", "drift_metrics[]" }`. |
| **5.2** Sink abstraction | `hb/alerting/__init__.py`, `hb/alerting/sinks/base.py` | `AlertSink.emit(event)`. Implementations: `StdoutSink`, `FileSink`, `SyslogSink`, `WebhookSink` (POST JSON). |
| **5.3** `hb alert` CLI (or daemon-integrated) | `hb/cli.py` or daemon | `hb alert --sink stdout|file|syslog|webhook` (or in daemon config: `alert_sinks: [file, webhook]`). On drift/FAIL, daemon calls sinks with the event. |
| **5.4** Severity routing | `hb/alerting/severity.py` | Map status + fail_metrics to WARN / FAIL / CRITICAL; optional config so certain metrics elevate to CRITICAL. |

**Acceptance:** Daemon detects drift → writes alert event to file and/or stdout; optional webhook POST to a test URL succeeds with the same JSON.

---

### 6) Evidence pack automation

**Goal:** On FAIL (or on demand), HB produces a forensic-ready evidence pack.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **6.1** Evidence pack layout | `hb/evidence.py` | Define layout: `evidence_<case_id>/` with `raw_telemetry_slice.jsonl`, `normalized_metrics.csv`, `config_snapshot/` (registry, baseline_policy, daemon config), `drift_report.json`, `drift_report.html`, `audit_log.jsonl`, `manifest.json`. |
| **6.2** Auto-trigger on FAIL | `hb/daemon.py` (or analyze path) | When status is FAIL, call `export_evidence_pack(case_id, report_dir, ...)` automatically (or via config flag). |
| **6.3** `hb export evidence-pack` | `hb/cli.py` | `hb export evidence-pack --case <run_id> --report-dir <path> --out ./evidence_packs/`. Gathers report, config, and optional raw slice into one directory/zip. |
| **6.4** Optional: zip and sign | `hb/evidence.py` | `--out ./evidence_packs/case_xyz.zip`; optional `--sign-key` for signature. |

**Acceptance:** After a FAIL run, `hb export evidence-pack --case <run_id> --report-dir ... --out ./out` produces a folder (or zip) containing report, config, and manifest; support bundle can reference it.

---

### 7) Fault injection (minimal, for demos)

**Goal:** Intentionally induce failures so “HB detects drift” is demonstrable without real hardware.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **7.1** Fault injector module | `hb/inject/__init__.py`, `hb/inject/faults.py` | Fault types: `latency_spike`, `packet_loss`, `schema_change` (rename/drop metric), `value_corruption` (noise or offset). Each fault is a small function that modifies a stream or a one-off file. |
| **7.2** `hb inject` CLI | `hb/cli.py` | `hb inject --fault latency_spike --input ./normalized.csv --output ./corrupted.csv --param delay_ms=500` (or inject into a live stream in tests). |
| **7.3** File-replay + inject in demo | `tools/demo_daemon.sh` | Script: start MQTT broker (e.g. mosquitto), publish clean telemetry for 2 min, then publish “faulty” telemetry; daemon should report drift. |

**Acceptance:** `hb inject --fault value_corruption --input ... --output ...` produces a CSV that when compared to baseline yields drift; demo script runs daemon and shows one drift event.

---

### 8) Reliability + resilience

**Goal:** HB survives reboot / crash mid-stream; no corruption; bounded disk usage.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **8.1** Checkpointing for ingest | `hb/daemon.py` or `hb/ingest/` | After each successful ingest window, write checkpoint (e.g. last timestamp or offset) to `daemon_checkpoint.json`. On start, resume from checkpoint if present. |
| **8.2** DB durability | Existing SQLite usage in `hb/registry.py` | Ensure `PRAGMA journal_mode=WAL` and sync; document or config for path. Optional: config for Postgres for multi-node later. |
| **8.3** Disk caps + log rotation | `hb/daemon.py` or config | Config: `max_report_dir_mb`, `max_audit_log_mb`. Rotate or prune oldest reports/audit when over limit. |
| **8.4** “Survives restart” test | `tests/test_daemon_resilience.py` | Start daemon, ingest some data, kill process, restart; assert no corruption and next run continues from checkpoint. |

**Acceptance:** Kill `hb daemon` mid-run; restart; daemon resumes and next drift check uses data after checkpoint. Report dir size stays under configured cap.

---

### 9) Secure local deployment defaults

**Goal:** Install and run as non-root with locked-down permissions; DoD-friendly defaults.

| Task | Files / Modules | Deliverable |
|------|-----------------|-------------|
| **9.1** `install.sh` (or install script) | `deploy/install.sh` or `tools/install.sh` | Create `hb` user (or use existing), install to `/opt/hb` or configurable prefix, set ownership of config/reports/db to `hb`, no root. |
| **9.2** systemd unit hardening | `deploy/hb-daemon.service` | `PrivateTmp=yes`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ReadWritePaths=...`, `User=hb`. |
| **9.3** Permissions on reports + DB | Install script + docs | Reports dir and DB dir: `chmod 750`, owner `hb`. Document in `docs/SECURE_INSTALL.md`. |
| **9.4** Optional: mTLS placeholder | Docs only for now | Document that node agents (future) can use mTLS to talk to HB core; no implementation in 2-week sprint. |

**Acceptance:** `sudo ./deploy/install.sh` (or equivalent) results in HB installed and daemon running as non-root; report/db dirs not writable by others.

---

### 10) WaveOS integration (out of scope for 2-week sprint)

**Defer to follow-on:** Define API contract (HB → WaveOS health events, WaveOS → HB policy), event schema (JSON Schema or .proto), and a thin `waveos` adapter module. No implementation in this sprint; only a short design note in `docs/WAVEOS_INTEGRATION.md` with “TODO: event schema, adapter.”

---

## Suggested Day-by-Day (2-Week)

| Day | Focus |
|-----|--------|
| **D1** | Ingest adapter interface + file-replay adapter; CLI `--source file-replay`. |
| **D2** | MQTT adapter + CLI; optional syslog stub. |
| **D3** | Telemetry schema YAML + `hb normalize`; wire into ingest so normalized output matches registry. |
| **D4** | `hb baseline create --window 24h` + versioning in DB; `hb baseline promote`. |
| **D5** | `hb daemon` skeleton: config, loop, ingest + 5-min window compare, write report; systemd template. |
| **D6** | Alert sink (stdout, file, webhook); daemon emits alert on drift/FAIL. |
| **D7** | Evidence pack layout + `hb export evidence-pack`; auto-trigger on FAIL from daemon. |
| **D8** | Fault injector (value_corruption, schema_change) + `hb inject`; demo script. |
| **D9** | Checkpointing + resume; DB durability; disk caps. |
| **D10** | install.sh + systemd hardening; “survives restart” test; doc updates. |

---

## File / Module Map (New or Touched)

| Path | Purpose |
|------|--------|
| `hb/ingest/__init__.py` | Source registry; `get_source(name)` → adapter instance. |
| `hb/ingest/sources/base.py` | Base class for ingest sources. |
| `hb/ingest/sources/file_replay.py` | Replay from file with optional speed limit. |
| `hb/ingest/sources/mqtt.py` | MQTT subscribe → normalized events. |
| `hb/ingest/sources/syslog.py` | Syslog/journald → structured events. |
| `config/telemetry_schema.yaml` | Field mapping, unit conversion, topic/pattern config. |
| `hb/normalize.py` | `normalize_telemetry(raw, schema)` → canonical metrics. |
| `hb/baseline.py` | `create_baseline(window, run_ids)`; versioning helpers. |
| `hb/daemon.py` | Daemon loop; config load; ingest → buffer → periodic compare → report + alert. |
| `config/daemon.yaml` | Daemon config schema. |
| `hb/alerting/__init__.py`, `sinks/*.py` | Sink interface + stdout/file/syslog/webhook. |
| `hb/evidence.py` | Evidence pack layout and export. |
| `hb/inject/__init__.py`, `hb/inject/faults.py` | Fault injection. |
| `deploy/hb-daemon.service` | systemd unit. |
| `deploy/install.sh` | Install + hardening. |
| `schemas/alert_event.json` | Alert event JSON schema. |
| `docs/WAVEOS_INTEGRATION.md` | Placeholder design for WaveOS adapter. |

---

## Success Criteria for “Pilot Ready” (End of 2-Week Sprint)

1. **`hb daemon`** runs 24 hours on a laptop with **file-replay** (or MQTT) telemetry without crashing.
2. **Baseline** is created (e.g. first 24h or manual `hb baseline create`) and **drift** is detected when telemetry changes (e.g. after fault injection).
3. **Alerts** are emitted to at least one sink (file or stdout); optional webhook.
4. **Evidence pack** is auto-generated on FAIL (or on demand via `hb export evidence-pack`).
5. **Restart:** Daemon survives kill + restart and resumes from checkpoint.
6. **Install:** `install.sh` (or equivalent) sets non-root, systemd, and permissions so the deployment is “hardened” by default.

When these are done, the gap between “demo software” and “pilot software” is closed enough to justify buying hardware for a real telemetry pilot.
