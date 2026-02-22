"""
Evidence pack: forensic-ready bundle on FAIL (or on demand).
Layout: evidence_<case_id>/ with raw_telemetry_slice, normalized_metrics.csv, config_snapshot/, drift_report.*, manifest.json.
"""
import json
import os
import shutil
from datetime import datetime, timezone


def export_evidence_pack(
    case_id: str,
    report_dir: str,
    out_path: str,
    config_paths: dict | None = None,
    raw_slice_path: str | None = None,
    zip_output: bool = False,
    redaction_policy_path: str | None = None,
    redaction_profile: str | None = None,
) -> str:
    """
    Gather report, config snapshot, optional raw slice into evidence_<case_id>/ or .zip.
    config_paths: {"metric_registry": path, "baseline_policy": path, "daemon": path}
    If redaction_policy_path and redaction_profile are set, apply that profile to run_meta before writing.
    Returns path to created dir or zip.
    """
    config_paths = config_paths or {}
    name = f"evidence_{case_id}"
    root = os.path.join(out_path, name)
    os.makedirs(root, exist_ok=True)

    # Copy report (optionally redact run_meta)
    run_meta_src = os.path.join(report_dir, "run_meta_normalized.json")
    run_meta_dst = os.path.join(root, "run_meta_normalized.json")
    if redaction_policy_path and redaction_profile and os.path.isfile(run_meta_src):
        from hb.redaction import apply_redaction
        with open(run_meta_src) as f:
            run_meta = json.load(f)
        apply_redaction(redaction_policy_path, run_meta, profile=redaction_profile)
        with open(run_meta_dst, "w") as f:
            json.dump(run_meta, f, indent=2)
    elif os.path.isfile(run_meta_src):
        shutil.copy2(run_meta_src, run_meta_dst)
    for f in ["drift_report.json", "drift_report.html", "metrics_normalized.csv"]:
        src = os.path.join(report_dir, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(root, f))

    # Config snapshot
    config_dir = os.path.join(root, "config_snapshot")
    os.makedirs(config_dir, exist_ok=True)
    for label, path in config_paths.items():
        if path and os.path.isfile(path):
            shutil.copy2(path, os.path.join(config_dir, os.path.basename(path)))

    # Raw telemetry slice
    if raw_slice_path and os.path.isfile(raw_slice_path):
        shutil.copy2(raw_slice_path, os.path.join(root, "raw_telemetry_slice.jsonl"))

    # Manifest
    manifest = {
        "case_id": case_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": report_dir,
        "config_paths": list(config_paths.keys()),
    }
    with open(os.path.join(root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    if zip_output:
        zip_path = shutil.make_archive(root, "zip", out_path, name)
        shutil.rmtree(root, ignore_errors=True)
        return zip_path
    return root
