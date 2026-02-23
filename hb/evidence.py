"""
Evidence pack: forensic-ready bundle on FAIL (or on demand).
Layout: evidence_<case_id>/ with raw_telemetry_slice, normalized_metrics.csv, config_snapshot/, drift_report.*, manifest.json.
Supports compression (gzip-level zip) and tiered retention.
"""
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from typing import Any


def export_evidence_pack(
    case_id: str,
    report_dir: str,
    out_path: str,
    config_paths: dict | None = None,
    raw_slice_path: str | None = None,
    zip_output: bool = False,
    redaction_policy_path: str | None = None,
    redaction_profile: str | None = None,
    baseline_snapshot_path: str | None = None,
    actions_policy_path: str | None = None,
    decision_record_path: str | None = None,
    sbom_hash: str | None = None,
    code_version: str | None = None,
) -> str:
    """
    Full reproduction bundle: input slice, baseline snapshot, metric registry, policy snapshot,
    decision record, code/SBOM hash. Enables "re-run and get same answer."
    config_paths: {"metric_registry": path, "baseline_policy": path, "daemon": path}
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

    # Decision record (first-class artifact)
    dr_src = decision_record_path or os.path.join(report_dir, "decision_record.json")
    if os.path.isfile(dr_src):
        shutil.copy2(dr_src, os.path.join(root, "decision_record.json"))

    # Config snapshot (metric registry, baseline policy, optional actions policy)
    config_dir = os.path.join(root, "config_snapshot")
    os.makedirs(config_dir, exist_ok=True)
    for label, path in config_paths.items():
        if path and os.path.isfile(path):
            shutil.copy2(path, os.path.join(config_dir, os.path.basename(path)))
    if actions_policy_path and os.path.isfile(actions_policy_path):
        shutil.copy2(actions_policy_path, os.path.join(config_dir, "actions_policy.yaml"))

    # Baseline snapshot (for reproduction)
    if baseline_snapshot_path and os.path.isfile(baseline_snapshot_path):
        shutil.copy2(baseline_snapshot_path, os.path.join(root, "baseline_snapshot.json"))

    # Raw telemetry slice (input slice)
    if raw_slice_path and os.path.isfile(raw_slice_path):
        shutil.copy2(raw_slice_path, os.path.join(root, "raw_telemetry_slice.jsonl"))

    # Manifest with full reproduction fields
    manifest = {
        "case_id": case_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "report_dir": report_dir,
        "config_paths": list(config_paths.keys()),
        "artifacts": [
            "drift_report.json",
            "drift_report.html",
            "metrics_normalized.csv",
            "run_meta_normalized.json",
            "decision_record.json",
            "config_snapshot",
            "raw_telemetry_slice.jsonl",
            "baseline_snapshot.json",
        ],
        "sbom_hash": sbom_hash or os.environ.get("HB_SBOM_HASH", ""),
        "code_version": code_version or os.environ.get("HB_VERSION", "dev"),
    }
    with open(os.path.join(root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    if zip_output:
        zip_path = os.path.join(out_path, f"{name}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for dirpath, _, filenames in os.walk(root):
                for f in filenames:
                    full = os.path.join(dirpath, f)
                    arcname = os.path.join(name, os.path.relpath(full, root))
                    zf.write(full, arcname)
        shutil.rmtree(root, ignore_errors=True)
        return zip_path
    return root
