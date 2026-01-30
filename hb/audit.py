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
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        pass
    return out_path


def _entry_hash(entry, prev_hash):
    payload = dict(entry)
    payload.pop("entry_hash", None)
    payload["prev_hash"] = prev_hash
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def append_audit_log(report_dir, run_id, action, details):
    os.makedirs(report_dir, exist_ok=True)
    log_path = os.path.join(report_dir, "audit_log.jsonl")
    prev_hash = None
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            lines = [line for line in f.read().splitlines() if line.strip()]
        if lines:
            try:
                prev_entry = json.loads(lines[-1])
                prev_hash = prev_entry.get("entry_hash")
            except json.JSONDecodeError:
                prev_hash = None
    payload = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "action": action,
        "details": details,
    }
    payload["prev_hash"] = prev_hash
    payload["entry_hash"] = _entry_hash(payload, prev_hash)
    with open(log_path, "a") as f:
        f.write(json.dumps(payload) + "\n")
    try:
        os.chmod(log_path, 0o600)
    except OSError:
        pass
    return log_path


def verify_artifact_manifest(manifest_path):
    if not os.path.exists(manifest_path):
        return ["manifest not found"]
    with open(manifest_path, "r") as f:
        entries = json.load(f)
    issues = []
    for entry in entries:
        path = entry.get("path")
        expected = entry.get("sha256")
        if not path or not expected:
            issues.append("manifest entry missing path/sha256")
            continue
        if not os.path.exists(path):
            issues.append(f"missing artifact: {path}")
            continue
        actual = file_hash(path)
        if actual != expected:
            issues.append(f"hash mismatch: {path}")
    return issues


def verify_audit_log(log_path, strict=False):
    if not os.path.exists(log_path):
        return ["audit log not found"]
    issues = []
    prev_hash = None
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                issues.append("invalid JSON entry")
                if strict:
                    return issues
                continue
            expected = entry.get("entry_hash")
            if not expected:
                msg = "entry missing entry_hash"
                if strict:
                    issues.append(msg)
                    return issues
                prev_hash = None
                continue
            computed = _entry_hash(entry, prev_hash)
            if computed != expected:
                issues.append("audit hash mismatch")
                if strict:
                    return issues
            prev_hash = expected
    return issues
