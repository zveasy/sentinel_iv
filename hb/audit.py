import hashlib
import json
import os
from datetime import datetime, timezone


def file_hash(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_artifact_manifest(report_dir, files):
    manifest = []
    for path in files:
        if not path or not os.path.exists(path):
            continue
        manifest.append(
            {
                "path": os.path.abspath(path),
                "sha256": file_hash(path),
            }
        )
    out_path = os.path.join(report_dir, "artifact_manifest.json")
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    return out_path


def append_audit_log(report_dir, run_id, action, details):
    os.makedirs(report_dir, exist_ok=True)
    log_path = os.path.join(report_dir, "audit_log.jsonl")
    payload = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "action": action,
        "details": details,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(payload) + "\n")
    return log_path
