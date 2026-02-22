"""
Daemon: continuous ingest + periodic drift check. Checkpointing and disk caps.
hb daemon --config config/daemon.yaml
"""
import os
import sys
import time
import json
from datetime import datetime, timezone

import yaml

# Import here so daemon can run without full CLI
from hb.ingest import get_source
from hb.normalize import load_telemetry_schema, normalize_telemetry, aggregate_to_metrics
from hb.config import load_metric_registry, load_baseline_policy
from hb.registry import init_db, fetch_metrics, select_baseline, replace_metrics, upsert_run
from hb.engine import normalize_metrics, compare_metrics
from hb.io import read_json, write_json, write_metrics_csv
from hb.report import write_report
from hb.alerting import severity_for_status
from hb.evidence import export_evidence_pack
from hb.resilience import save_checkpoint_to_history, CircuitBreaker

CHECKPOINT_FILENAME = "daemon_checkpoint.json"

_circuit_breaker = None


def _get_circuit_breaker(config):
    global _circuit_breaker
    cb_config = config.get("circuit_breaker")
    if not cb_config:
        return None
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(
            failure_threshold=int(cb_config.get("failure_threshold", 5)),
            window_sec=float(cb_config.get("window_sec", 60)),
            open_sec=float(cb_config.get("open_sec", 30)),
        )
    return _circuit_breaker


def _read_metrics_csv(path):
    import csv
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "r", newline="") as f:
        for row in csv.DictReader(f):
            out.append(row)
    return out


def _metrics_to_rows(metrics_current):
    return [
        {"metric": m, "value": d["value"], "unit": d.get("unit") or "", "tags": d.get("tags") or ""}
        for m in sorted(metrics_current.keys())
        for d in [metrics_current[m]]
    ]


def load_daemon_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def run_daemon_cycle(config: dict, buffer: list, checkpoint: dict) -> tuple[str, str | None]:
    """
    One cycle: aggregate buffer to metrics, compare to baseline, write report.
    Returns (status, report_dir).
    """
    cfg = config
    output_dir = os.path.abspath(cfg.get("output_dir", "daemon_output"))
    db_path = cfg.get("db_path", "runs.db")
    metric_registry_path = cfg.get("metric_registry", "metric_registry.yaml")
    baseline_policy_path = cfg.get("baseline_policy", "baseline_policy.yaml")
    schema_path = cfg.get("telemetry_schema", "config/telemetry_schema.yaml")
    baseline_tag = cfg.get("baseline_tag", "golden")

    schema = load_telemetry_schema(schema_path) if os.path.isfile(schema_path) else {}
    normalized = normalize_telemetry(buffer, schema)
    metrics_raw = aggregate_to_metrics(normalized, strategy="last")
    if not metrics_raw:
        return "NO_DATA", None

    registry = load_metric_registry(metric_registry_path, program=None)
    metrics_current, _ = normalize_metrics(metrics_raw, registry)

    run_id = f"daemon_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{len(buffer)}"
    import uuid as _uuid
    run_meta = {
        "run_id": run_id,
        "correlation_id": os.environ.get("HB_CORRELATION_ID") or str(_uuid.uuid4()),
        "program": None,
        "toolchain": {"source_system": "daemon"},
        "timestamps": {"start_utc": "", "end_utc": datetime.now(timezone.utc).isoformat()},
        "build": {},
    }

    policy = load_baseline_policy(baseline_policy_path)
    policy["tag"] = baseline_tag  # use daemon's baseline_tag for baseline selection
    registry_hash = None
    if os.path.isfile(metric_registry_path):
        import hashlib
        with open(metric_registry_path, "rb") as f:
            registry_hash = hashlib.sha256(f.read()).hexdigest()[:16]
    policy_hash = None
    if os.path.isfile(baseline_policy_path):
        import hashlib
        with open(baseline_policy_path, "rb") as f:
            policy_hash = hashlib.sha256(f.read()).hexdigest()[:16]

    conn = init_db(db_path)
    baseline_run_id, baseline_reason, baseline_warning, baseline_match = select_baseline(
        conn, run_meta, policy, registry_hash=registry_hash
    )
    baseline_metrics = fetch_metrics(conn, baseline_run_id) if baseline_run_id else {}

    status, drift_metrics, warnings, fail_metrics, invariant_violations, distribution_drifts, drift_attribution = compare_metrics(
        metrics_current, baseline_metrics, registry, distribution_enabled=policy.get("distribution_drift_enabled", True), plan=None, early_exit=False, deterministic=True
    )

    report_dir = os.path.join(output_dir, run_id)
    os.makedirs(report_dir, exist_ok=True)
    write_json(os.path.join(report_dir, "run_meta_normalized.json"), run_meta)
    write_metrics_csv(os.path.join(report_dir, "metrics_normalized.csv"), _metrics_to_rows(metrics_current))

    report_payload = {
        "run_id": run_id,
        "correlation_id": run_meta.get("correlation_id"),
        "status": status,
        "baseline_run_id": baseline_run_id,
        "baseline_reason": baseline_reason,
        "baseline_warning": baseline_warning,
        "drift_metrics": drift_metrics or [],
        "top_drifts": (drift_metrics or [])[:10],
        "fail_metrics": fail_metrics or [],
        "invariant_violations": invariant_violations or [],
        "warnings": warnings or [],
        "drift_attribution": {"top_drivers": drift_attribution or []},
    }
    write_report(report_dir, report_payload)

    upsert_run(conn, run_meta, status, baseline_run_id=baseline_run_id, registry_hash=registry_hash)
    replace_metrics(conn, run_id, _metrics_to_rows(metrics_current))
    conn.close()

    # Alerts
    sink_names = [s.strip().lower() for s in (cfg.get("alert_sinks") or ["stdout"])]
    alert_path = os.path.join(output_dir, "alerts.jsonl")
    sev = severity_for_status(status, fail_metrics or [])
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "severity": sev,
        "status": status,
        "run_id": run_id,
        "primary_issue": "drift" if drift_metrics else ("fail" if fail_metrics else "ok"),
        "report_path": report_dir,
        "drift_metrics": (drift_metrics or [])[:10],
    }
    if "stdout" in sink_names:
        from hb.alerting.sinks.stdout_sink import StdoutSink
        try:
            StdoutSink().emit(event)
        except Exception as e:
            print(f"alert stdout error: {e}", file=sys.stderr)
    if "file" in sink_names:
        from hb.alerting.sinks.file_sink import FileSink
        try:
            FileSink(path=alert_path).emit(event)
        except Exception as e:
            print(f"alert file error: {e}", file=sys.stderr)
    if "webhook" in sink_names and cfg.get("webhook_url"):
        from hb.alerting.sinks.webhook_sink import WebhookSink
        try:
            WebhookSink(url=cfg["webhook_url"]).emit(event)
        except Exception as e:
            print(f"alert webhook error: {e}", file=sys.stderr)

    # Evidence pack on FAIL or always (e.g. for HIL/SIL: every run)
    if (status == "FAIL" and cfg.get("evidence_pack_on_fail")) or cfg.get("evidence_pack_always"):
        try:
            export_evidence_pack(
                run_id,
                report_dir,
                output_dir,
                config_paths={
                    "metric_registry": metric_registry_path,
                    "baseline_policy": baseline_policy_path,
                },
            )
        except Exception as e:
            print(f"evidence pack error: {e}", file=sys.stderr)

    return status, report_dir


def prune_reports(output_dir: str, max_mb: float) -> None:
    """Remove oldest report dirs until total size <= max_mb."""
    if max_mb <= 0:
        return
    dirs = []
    for name in os.listdir(output_dir):
        path = os.path.join(output_dir, name)
        if os.path.isdir(path) and name.startswith("daemon_"):
            size = sum(os.path.getsize(os.path.join(r, f)) for r, _, files in os.walk(path) for f in files)
            dirs.append((path, size, os.path.getmtime(path)))
    dirs.sort(key=lambda x: x[2])
    total = sum(d[1] for d in dirs)
    max_bytes = max_mb * 1024 * 1024
    for path, size, _ in dirs:
        if total <= max_bytes:
            break
        try:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
            total -= size
        except OSError:
            pass


def daemon_main(config_path: str) -> None:
    config = load_daemon_config(config_path)
    source_type = config.get("source", "file_replay")
    path = config.get("path", "")
    interval_sec = int(config.get("interval_sec", 300))
    window_sec = int(config.get("window_sec", 300))
    output_dir = os.path.abspath(config.get("output_dir", "daemon_output"))
    max_report_mb = float(config.get("max_report_dir_mb", 0) or 0)
    checkpoint_path = os.path.join(output_dir, CHECKPOINT_FILENAME)

    os.makedirs(output_dir, exist_ok=True)
    buffer = []
    checkpoint = {}
    if os.path.isfile(checkpoint_path):
        try:
            with open(checkpoint_path, "r") as f:
                checkpoint = json.load(f)
        except Exception:
            pass

    if source_type == "file_replay" and not path:
        print("daemon: config path is empty for file_replay; set path in config", file=sys.stderr)
        sys.exit(1)

    print(f"daemon started: source={source_type} interval={interval_sec}s window={window_sec}s output={output_dir}")
    last_cycle = time.time()
    while True:
        try:
            now = time.time()
            if source_type == "file_replay" and path and os.path.isfile(path):
                source = get_source("file_replay", path=path, delay_sec=0)
                source.connect()
                events = source.read(limit=1000, timeout_sec=min(60, interval_sec))
                source.close()
                for e in events:
                    e["_ts"] = now
                buffer.extend(events)
            elif source_type == "mqtt":
                broker = config.get("broker", "tcp://localhost:1883")
                topic = config.get("topic", "hb/metrics/#")
                source = get_source("mqtt", broker=broker, topic=topic)
                try:
                    source.connect()
                    events = source.read(limit=100, timeout_sec=min(30, interval_sec))
                    for e in events:
                        e["_ts"] = now
                    buffer.extend(events)
                finally:
                    source.close()
            else:
                time.sleep(1)
                continue

            # Prune buffer to window
            cutoff = now - window_sec
            buffer = [e for e in buffer if e.get("_ts", 0) >= cutoff]

            if now - last_cycle >= interval_sec:
                breaker = _get_circuit_breaker(config)
                if breaker:
                    try:
                        status, report_dir = breaker.call(lambda: run_daemon_cycle(config, buffer, checkpoint))
                    except RuntimeError:
                        status, report_dir = "CIRCUIT_OPEN", None
                        print("daemon: circuit breaker open, skipping cycle", file=sys.stderr)
                else:
                    status, report_dir = run_daemon_cycle(config, buffer, checkpoint)
                last_cycle = now
                checkpoint["last_cycle_utc"] = datetime.now(timezone.utc).isoformat()
                checkpoint["last_status"] = status
                if report_dir:
                    checkpoint["last_report_dir"] = report_dir
                try:
                    with open(checkpoint_path, "w") as f:
                        json.dump(checkpoint, f, indent=2)
                    save_checkpoint_to_history(
                        output_dir,
                        checkpoint,
                        max_entries=int(config.get("max_checkpoint_history", 50)),
                    )
                except OSError:
                    pass
                if max_report_mb > 0:
                    prune_reports(output_dir, max_report_mb)
                print(f"cycle: status={status} report={report_dir or '-'}")
        except KeyboardInterrupt:
            print("daemon stopped")
            break
        except Exception as e:
            print(f"daemon error: {e}", file=sys.stderr)
            time.sleep(10)
