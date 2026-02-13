import json
import os
import platform
import tempfile
import zipfile
from datetime import datetime, timezone

from hb.config import load_baseline_policy, load_metric_registry
from hb.registry import init_db


def health_check(db_path, metric_registry, baseline_policy):
    checks = {}
    status = "ok"
    try:
        load_metric_registry(metric_registry)
        checks["metric_registry"] = "ok"
    except Exception as exc:
        checks["metric_registry"] = f"error: {exc}"
        status = "degraded"
    try:
        load_baseline_policy(baseline_policy)
        checks["baseline_policy"] = "ok"
    except Exception as exc:
        checks["baseline_policy"] = f"error: {exc}"
        status = "degraded"
    try:
        conn = init_db(db_path)
        conn.execute("SELECT 1")
        checks["registry_db"] = "ok"
    except Exception as exc:
        checks["registry_db"] = f"error: {exc}"
        status = "degraded"
    return {"status": status, "checks": checks}


def build_support_bundle(
    out_path,
    db_path,
    metric_registry,
    baseline_policy,
    report_dir=None,
):
    diagnostics = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "db_path": os.path.abspath(db_path),
        "metric_registry": os.path.abspath(metric_registry),
        "baseline_policy": os.path.abspath(baseline_policy),
    }
    diagnostics["health"] = health_check(db_path, metric_registry, baseline_policy)

    with tempfile.TemporaryDirectory() as tmpdir:
        diag_path = os.path.join(tmpdir, "diagnostics.json")
        with open(diag_path, "w") as f:
            json.dump(diagnostics, f, indent=2)

        files = [
            diag_path,
            metric_registry,
            baseline_policy,
            db_path,
        ]
        audit_candidates = [
            os.path.join("artifacts", "baseline_approvals.txt"),
            os.path.join("artifacts", "baseline_requests.txt"),
        ]
        for path in audit_candidates:
            if os.path.exists(path):
                files.append(path)
        if report_dir:
            for name in ("drift_report.json", "drift_report.html", "audit_log.jsonl", "perf.json"):
                path = os.path.join(report_dir, name)
                if os.path.exists(path):
                    files.append(path)

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                if not path or not os.path.exists(path):
                    continue
                arcname = os.path.basename(path)
                zf.write(path, arcname)
    return out_path
