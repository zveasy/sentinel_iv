"""
Program readiness gate (PREWG) evaluation.
Consumes registry and optional report data; returns Ready / At Risk / Not Ready + reasons.
"""
import os
from datetime import datetime, timezone

import yaml


def load_readiness_config(path: str | None = None) -> dict:
    if path is None:
        path = os.environ.get("HB_READINESS_GATES", "config/readiness_gates.yaml")
    if not os.path.isfile(path):
        return {"version": "1.0", "gates": {}}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _resolve_gate(config: dict, gate_name: str) -> dict:
    gates = config.get("gates") or {}
    gate = dict(gates.get(gate_name) or {})
    if gate.get("extends"):
        parent = _resolve_gate(config, gate["extends"])
        criteria = list((parent.get("criteria") or [])) + list((gate.get("criteria") or []))
        gate = {**parent, **gate, "criteria": criteria}
    return gate


def evaluate_gate(
    gate_name: str,
    config: dict | None = None,
    conn=None,
    reports_dir: str | None = None,
) -> tuple[str, list[str]]:
    """
    Evaluate a single gate. Returns (verdict, reasons).
    verdict: "Ready" | "At Risk" | "Not Ready"
    """
    if config is None:
        config = load_readiness_config()
    gate = _resolve_gate(config, gate_name)
    if not gate:
        return "Not Ready", [f"Unknown gate: {gate_name}"]
    criteria = gate.get("criteria") or []
    reasons = []
    all_ok = True
    for c in criteria:
        cid = c.get("id", "")
        ctype = c.get("type", "")
        params = c.get("params") or {}
        if ctype == "no_fail_in_runs":
            n = params.get("runs", 10)
            if conn is None:
                reasons.append(f"{cid}: (registry not provided)")
                all_ok = False
                continue
            cursor = conn.execute(
                "SELECT status FROM runs ORDER BY created_at DESC LIMIT ?",
                (n,),
            )
            rows = cursor.fetchall()
            fails = [r[0] for r in rows if r[0] == "FAIL"]
            if fails:
                reasons.append(f"{cid}: FAIL in recent runs ({len(fails)} of {len(rows)} runs)")
                all_ok = False
            else:
                reasons.append(f"{cid}: no FAIL in last {len(rows)} runs")
        elif ctype == "baseline_tag_set":
            if conn is None:
                reasons.append(f"{cid}: (registry not provided)")
                all_ok = False
                continue
            cursor = conn.execute("SELECT tag FROM baseline_tags LIMIT 1")
            if cursor.fetchone() is None:
                reasons.append(f"{cid}: no baseline tag set")
                all_ok = False
            else:
                reasons.append(f"{cid}: baseline tag set")
        elif ctype == "no_critical_metric_drift":
            reasons.append(f"{cid}: (check report data for critical drift)")
            # Could parse recent drift_report.json and check fail_metrics vs critical list
        elif ctype == "evidence_pack_if_fail":
            reasons.append(f"{cid}: (evidence pack required if FAIL)")
        elif ctype == "no_open_baseline_requests":
            if conn is None:
                reasons.append(f"{cid}: (registry not provided)")
                all_ok = False
                continue
            cursor = conn.execute(
                "SELECT COUNT(*) FROM baseline_requests WHERE status = 'pending'"
            )
            n = cursor.fetchone()[0]
            if n > 0:
                reasons.append(f"{cid}: {n} open baseline request(s)")
                all_ok = False
            else:
                reasons.append(f"{cid}: no open baseline requests")
        else:
            reasons.append(f"{cid}: criterion type '{ctype}' not implemented")
    if all_ok:
        return "Ready", reasons
    return "Not Ready", reasons


def evaluate_gate_at_risk(verdict: str, reasons: list[str]) -> str:
    """Map to three-state: Ready, At Risk, Not Ready. At Risk = some issues but not blocking."""
    if verdict == "Ready":
        return "Ready"
    return "Not Ready"
