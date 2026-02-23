#!/usr/bin/env python3
"""
Reference client for emitting and consuming HB_EVENT (schemas/hb_event.json).
Use from lab harness, Jenkins, or telemetry bus integrations.
Emits: DRIFT_EVENT, HEALTH_EVENT, ACTION_REQUEST, DECISION_SNAPSHOT.
Consumes: ACTION_ACK (e.g. from WaveOS or HB action executor).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Optional: Kafka producer for sink=kafka
try:
    from kafka import KafkaProducer
    _KAFKA_AVAILABLE = True
except ImportError:
    _KAFKA_AVAILABLE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_drift_event(
    system_id: str,
    status: str = "PASS",
    severity: str = "info",
    recommended_action: str | None = None,
    run_id: str | None = None,
    decision_id: str | None = None,
    confidence: float | None = None,
    baseline_confidence: float | None = None,
    action_allowed: bool = True,
    drift_metrics: list | None = None,
    report_path: str | None = None,
    payload: dict | None = None,
) -> dict:
    """Build HB_EVENT of type DRIFT_EVENT."""
    ev = {
        "type": "DRIFT_EVENT",
        "timestamp": _now_iso(),
        "system_id": system_id,
        "status": status,
        "severity": severity,
    }
    if recommended_action is not None:
        ev["recommended_action"] = recommended_action
    if run_id is not None:
        ev["run_id"] = run_id
    if decision_id is not None:
        ev["decision_id"] = decision_id
    if confidence is not None:
        ev["confidence"] = confidence
    if baseline_confidence is not None:
        ev["baseline_confidence"] = baseline_confidence
    ev["action_allowed"] = action_allowed
    if drift_metrics is not None:
        ev["drift_metrics"] = drift_metrics
    if report_path is not None:
        ev["report_path"] = report_path
    if payload is not None:
        ev["payload"] = payload
    return ev


def build_health_event(
    system_id: str,
    status: str = "PASS",
    primary_issue: str | None = None,
    run_id: str | None = None,
    severity: str = "info",
) -> dict:
    """Build HB_EVENT of type HEALTH_EVENT."""
    ev = {
        "type": "HEALTH_EVENT",
        "timestamp": _now_iso(),
        "system_id": system_id,
        "status": status,
        "severity": severity,
    }
    if primary_issue is not None:
        ev["primary_issue"] = primary_issue
    if run_id is not None:
        ev["run_id"] = run_id
    return ev


def build_action_request(
    system_id: str,
    action_type: str,
    action_id: str | None = None,
    confidence: float | None = None,
    action_allowed: bool = True,
    payload: dict | None = None,
) -> dict:
    """Build HB_EVENT of type ACTION_REQUEST."""
    import uuid
    ev = {
        "type": "ACTION_REQUEST",
        "timestamp": _now_iso(),
        "system_id": system_id,
        "action_type": action_type,
        "action_id": action_id or str(uuid.uuid4()),
        "action_allowed": action_allowed,
    }
    if confidence is not None:
        ev["confidence"] = confidence
    if payload is not None:
        ev["payload"] = payload
    return ev


def emit_stdout(ev: dict) -> None:
    """Emit one event as JSON line to stdout (for pipe or file_replay)."""
    print(json.dumps(ev), flush=True)


def emit_file(ev: dict, path: str) -> None:
    """Append one event as JSON line to file."""
    with open(path, "a") as f:
        f.write(json.dumps(ev) + "\n")


def emit_kafka(ev: dict, broker: str, topic: str) -> None:
    """Publish event to Kafka topic."""
    if not _KAFKA_AVAILABLE:
        raise RuntimeError("kafka-python not installed; pip install kafka-python")
    producer = KafkaProducer(
        bootstrap_servers=broker.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    producer.send(topic, value=ev)
    producer.flush()
    producer.close()


def main():
    ap = argparse.ArgumentParser(description="HB_EVENT reference client: emit events (use 'emit' or default)")
    ap.add_argument("cmd", nargs="?", default="emit", choices=["emit"], help="Command (default: emit)")
    ap.add_argument("--type", default="DRIFT_EVENT", choices=["DRIFT_EVENT", "HEALTH_EVENT", "ACTION_REQUEST", "DECISION_SNAPSHOT"], help="Event type")
    ap.add_argument("--system-id", default="asset-001", help="system_id")
    ap.add_argument("--status", default="PASS", choices=["PASS", "PASS_WITH_DRIFT", "FAIL"], help="Status (for DRIFT_EVENT)")
    ap.add_argument("--severity", default="info", choices=["info", "low", "medium", "high", "critical"])
    ap.add_argument("--recommended-action", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--decision-id", default=None)
    ap.add_argument("--confidence", type=float, default=None)
    ap.add_argument("--baseline-confidence", type=float, default=None)
    ap.add_argument("--action-allowed", type=lambda x: x.lower() == "true", default=True)
    ap.add_argument("--action-type", default="notify", help="For ACTION_REQUEST")
    ap.add_argument("--sink", default="stdout", choices=["stdout", "file", "kafka"], help="Where to emit")
    ap.add_argument("--out-file", default=None, help="For sink=file")
    ap.add_argument("--broker", default="localhost:9092", help="For sink=kafka")
    ap.add_argument("--topic", default="hb/events", help="For sink=kafka")
    args = ap.parse_args()

    if args.type == "DRIFT_EVENT":
        ev = build_drift_event(
            system_id=args.system_id,
            status=args.status,
            severity=args.severity,
            recommended_action=args.recommended_action,
            run_id=args.run_id,
            decision_id=args.decision_id,
            confidence=args.confidence,
            baseline_confidence=args.baseline_confidence,
            action_allowed=args.action_allowed,
        )
    elif args.type == "HEALTH_EVENT":
        ev = build_health_event(
            system_id=args.system_id,
            status=args.status,
            severity=args.severity,
            run_id=args.run_id,
        )
    elif args.type == "ACTION_REQUEST":
        ev = build_action_request(
            system_id=args.system_id,
            action_type=args.action_type,
            confidence=args.confidence,
            action_allowed=args.action_allowed,
        )
    else:
        ev = {
            "type": args.type,
            "timestamp": _now_iso(),
            "system_id": args.system_id,
            "severity": args.severity,
        }

    if args.sink == "stdout":
        emit_stdout(ev)
    elif args.sink == "file":
        path = args.out_file or "hb_events.jsonl"
        emit_file(ev, path)
    elif args.sink == "kafka":
        emit_kafka(ev, args.broker, args.topic)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
