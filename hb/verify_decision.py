"""
Independent verification mode: re-run compare from evidence pack and confirm same decision.
For auditors: hb verify-decision --decision decision_record.json --evidence evidence_pack/
"""
import hashlib
import json
import os
from typing import Any

from hb.replay import replay_decision, _load_metrics_from_path


def _find_in_evidence(evidence_dir: str, *names: str) -> str | None:
    for n in names:
        p = os.path.join(evidence_dir, n)
        if os.path.isfile(p):
            return p
    config_dir = os.path.join(evidence_dir, "config_snapshot")
    if os.path.isdir(config_dir):
        for f in os.listdir(config_dir):
            if f.endswith(".yaml") or f.endswith(".yml"):
                base = os.path.splitext(f)[0]
                if base in ("metric_registry", "baseline_policy") or "metric" in base or "baseline" in base:
                    return os.path.join(config_dir, f)
    return None


def verify_decision(
    decision_path: str,
    evidence_dir: str,
    out_dir: str | None = None,
) -> dict[str, Any]:
    """
    Load decision record and evidence pack; re-run compare; check hashes and same decision.
    evidence_dir: path to evidence_<case_id>/ (or dir containing decision_record.json and artifacts).
    Returns {"verified": bool, "match": bool, "reason": str, "replay_status": str, "decision_status": str, ...}.
    """
    if not os.path.isfile(decision_path):
        return {"verified": False, "match": False, "reason": "decision_record file not found", "decision_path": decision_path}
    with open(decision_path) as f:
        decision = json.load(f)
    decision_status = (decision.get("status") or "").strip()
    decision_config_hash = (decision.get("config_hash") or "").strip()

    # Resolve evidence dir: if decision_path is inside evidence_dir, use its parent
    if not os.path.isdir(evidence_dir):
        evidence_dir = os.path.dirname(decision_path)
    if not os.path.isdir(evidence_dir):
        return {"verified": False, "match": False, "reason": "evidence directory not found", "evidence_dir": evidence_dir}

    run_metrics_path = os.path.join(evidence_dir, "metrics_normalized.csv")
    if not os.path.isfile(run_metrics_path):
        return {"verified": False, "match": False, "reason": "metrics_normalized.csv not found in evidence", "evidence_dir": evidence_dir}

    baseline_path = os.path.join(evidence_dir, "baseline_snapshot.json")
    if not os.path.isfile(baseline_path):
        return {"verified": False, "match": False, "reason": "baseline_snapshot.json not found in evidence", "evidence_dir": evidence_dir}

    metric_registry_path = _find_in_evidence(evidence_dir, "config_snapshot/metric_registry.yaml", "config_snapshot/metric_registry.yml")
    if not metric_registry_path:
        for f in os.listdir(os.path.join(evidence_dir, "config_snapshot")) if os.path.isdir(os.path.join(evidence_dir, "config_snapshot")) else []:
            if "metric" in f.lower() and (f.endswith(".yaml") or f.endswith(".yml")):
                metric_registry_path = os.path.join(evidence_dir, "config_snapshot", f)
                break
    if not metric_registry_path or not os.path.isfile(metric_registry_path):
        return {"verified": False, "match": False, "reason": "metric_registry not found in evidence config_snapshot", "evidence_dir": evidence_dir}

    baseline_policy_path = _find_in_evidence(evidence_dir, "config_snapshot/baseline_policy.yaml", "config_snapshot/baseline_policy.yml")
    if not baseline_policy_path and os.path.isdir(os.path.join(evidence_dir, "config_snapshot")):
        for f in os.listdir(os.path.join(evidence_dir, "config_snapshot")):
            if "baseline" in f.lower() and (f.endswith(".yaml") or f.endswith(".yml")):
                baseline_policy_path = os.path.join(evidence_dir, "config_snapshot", f)
                break

    try:
        result = replay_decision(
            input_slice_path=run_metrics_path,
            baseline_path_or_run_id=baseline_path,
            metric_registry_path=metric_registry_path,
            baseline_policy_path=baseline_policy_path,
            db_path=None,
            out_dir=out_dir,
        )
    except Exception as e:
        return {"verified": False, "match": False, "reason": f"replay failed: {e}", "replay_status": None, "decision_status": decision_status}

    replay_status = (result.get("status") or "").strip()
    match = replay_status == decision_status

    # Optional: verify config hash from evidence matches decision
    config_ref = result.get("config_ref") or {}
    hashes = []
    if os.path.isfile(metric_registry_path):
        with open(metric_registry_path, "rb") as f:
            hashes.append(("metric_registry", hashlib.sha256(f.read()).hexdigest()))
    if baseline_policy_path and os.path.isfile(baseline_policy_path):
        with open(baseline_policy_path, "rb") as f:
            hashes.append(("baseline_policy", hashlib.sha256(f.read()).hexdigest()))
    computed_config_hash = hashlib.sha256(json.dumps(dict(hashes), sort_keys=True).encode()).hexdigest()
    hash_match = bool(decision_config_hash and computed_config_hash == decision_config_hash)

    verified = match and (hash_match or not decision_config_hash)
    reason = "deterministic replay matched" if verified else (
        "config hash mismatch" if not hash_match and decision_config_hash else f"status mismatch: replay={replay_status} decision={decision_status}"
    )

    return {
        "verified": verified,
        "match": match,
        "reason": reason,
        "replay_status": replay_status,
        "decision_status": decision_status,
        "config_hash_match": hash_match,
        "replay_config_ref": config_ref,
    }
