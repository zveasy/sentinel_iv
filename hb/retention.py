"""
Evidence and report retention: tiered retention (hot / warm / archive).
Compression and lifecycle by age.
"""
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone


def load_retention_config(path: str | None = None) -> dict:
    if not path:
        path = os.path.join(os.path.dirname(__file__), "..", "config", "retention.yaml")
    if not os.path.isfile(path):
        return {}
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("retention", data)


def _age_days(path: str) -> float:
    """Age in days from mtime or from manifest.json generated_utc."""
    if os.path.isfile(path):
        return (time.time() - os.path.getmtime(path)) / 86400
    if os.path.isdir(path):
        manifest = os.path.join(path, "manifest.json")
        if os.path.isfile(manifest):
            try:
                import json
                with open(manifest) as f:
                    m = json.load(f)
                ts = m.get("generated_utc")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
            except Exception:
                pass
        return (time.time() - os.path.getmtime(path)) / 86400
    return 0.0


def apply_retention(
    evidence_root: str,
    config: dict | None = None,
    dry_run: bool = True,
) -> dict:
    """
    Apply tiered retention to evidence packs under evidence_root.
    config: hot_days, warm_days, archive_days, after_archive (delete|archive), archive_dir.
    Returns { "processed": int, "deleted": [], "archived": [], "compressed": [], "errors": [] }.
    """
    config = config or load_retention_config()
    hot_days = config.get("hot_days", 7)
    warm_days = config.get("warm_days", 30)
    archive_days = config.get("archive_days", 365)
    after_archive = config.get("after_archive", "delete")
    archive_dir = config.get("archive_dir")

    result = {"processed": 0, "deleted": [], "archived": [], "compressed": [], "errors": []}
    if not os.path.isdir(evidence_root):
        return result

    for name in os.listdir(evidence_root):
        if not (name.startswith("evidence_") and (name.endswith(".zip") or os.path.isdir(os.path.join(evidence_root, name)))):
            continue
        path = os.path.join(evidence_root, name)
        age = _age_days(path)
        result["processed"] += 1
        try:
            if age > archive_days:
                if after_archive == "archive" and archive_dir:
                    dest = os.path.join(archive_dir, name)
                    if not dry_run:
                        os.makedirs(archive_dir, exist_ok=True)
                        shutil.move(path, dest)
                    result["archived"].append(name)
                else:
                    if not dry_run:
                        if os.path.isfile(path):
                            os.unlink(path)
                        else:
                            shutil.rmtree(path, ignore_errors=True)
                    result["deleted"].append(name)
            # warm: optional compression (dir -> zip) if not already zip; here we just log
            elif hot_days < age <= warm_days:
                if os.path.isdir(path) and not dry_run:
                    zip_path = os.path.join(evidence_root, name + ".zip")
                    if not os.path.isfile(zip_path):
                        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                            for dirpath, _, filenames in os.walk(path):
                                for f in filenames:
                                    full = os.path.join(dirpath, f)
                                    arcname = os.path.join(name, os.path.relpath(full, path))
                                    zf.write(full, arcname)
                        shutil.rmtree(path, ignore_errors=True)
                        result["compressed"].append(name)
        except Exception as e:
            result["errors"].append(f"{name}: {e}")
    return result
