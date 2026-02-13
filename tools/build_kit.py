import argparse
import os
import shutil
import zipfile


def _copytree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _read_version(template_dir):
    path = os.path.join(template_dir, "VERSION")
    with open(path, "r") as f:
        return f.read().strip()


def _zip_dir(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for name in files:
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, os.path.dirname(src_dir))
                zf.write(full_path, rel_path)


def main():
    parser = argparse.ArgumentParser(description="Build Hybrid Kit zip artifact.")
    parser.add_argument("--out-dir", default="artifacts", help="output directory for kit zip")
    parser.add_argument("--force", action="store_true", help="overwrite existing output")
    parser.add_argument("--checksums", action="store_true", help="generate checksum files for the zip after build")
    args = parser.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template_dir = os.path.join(root, "release", "hb-hybrid-kit")
    version = _read_version(template_dir)
    out_root = os.path.join(root, args.out_dir)
    _ensure_dir(out_root)

    kit_dir_name = f"hb-hybrid-kit-v{version}"
    kit_dir = os.path.join(out_root, kit_dir_name)
    if os.path.exists(kit_dir):
        if not args.force:
            raise RuntimeError(f"output already exists: {kit_dir}")
        shutil.rmtree(kit_dir)

    _copytree(template_dir, kit_dir)

    for path in ["hb", "hb_core", "app", "ingest", "schemas"]:
        _copytree(os.path.join(root, path), os.path.join(kit_dir, path))

    shutil.copy2(os.path.join(root, "bin", "hb"), os.path.join(kit_dir, "bin", "hb"))
    shutil.copy2(os.path.join(root, "metric_registry.yaml"), os.path.join(kit_dir, "metric_registry.yaml"))
    shutil.copy2(os.path.join(root, "baseline_policy.yaml"), os.path.join(kit_dir, "config", "thresholds.yaml"))

    examples_dir = os.path.join(kit_dir, "examples")
    baseline_case = os.path.join(root, "samples", "cases", "no_drift_pass")
    drift_case = os.path.join(root, "samples", "cases", "single_metric_drift")

    shutil.copy2(
        os.path.join(baseline_case, "baseline_source.csv"),
        os.path.join(examples_dir, "baseline", "baseline_source.csv"),
    )
    shutil.copy2(
        os.path.join(baseline_case, "baseline_run_meta.json"),
        os.path.join(examples_dir, "baseline", "baseline_run_meta.json"),
    )
    shutil.copy2(
        os.path.join(baseline_case, "current_source.csv"),
        os.path.join(examples_dir, "run_ok", "current_source.csv"),
    )
    shutil.copy2(
        os.path.join(baseline_case, "current_run_meta.json"),
        os.path.join(examples_dir, "run_ok", "current_run_meta.json"),
    )
    shutil.copy2(
        os.path.join(drift_case, "current_source.csv"),
        os.path.join(examples_dir, "run_drift", "current_source.csv"),
    )
    shutil.copy2(
        os.path.join(drift_case, "current_run_meta.json"),
        os.path.join(examples_dir, "run_drift", "current_run_meta.json"),
    )

    # Commercial-ready: customer-facing docs and changelog
    docs_src = os.path.join(root, "docs")
    docs_dst = os.path.join(kit_dir, "docs")
    _ensure_dir(docs_dst)
    for doc in [
        "THREAT_MODEL_CUSTOMER.md",
        "INTEGRITY_VERIFICATION.md",
        "SUPPORT.md",
        "SECURE_INSTALL.md",
        "OFFLINE_INSTALL.md",
    ]:
        src = os.path.join(docs_src, doc)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(docs_dst, doc))
    if os.path.isfile(os.path.join(root, "CHANGELOG.md")):
        shutil.copy2(os.path.join(root, "CHANGELOG.md"), os.path.join(kit_dir, "CHANGELOG.md"))

    zip_path = os.path.join(out_root, f"{kit_dir_name}.zip")
    if os.path.exists(zip_path) and args.force:
        os.remove(zip_path)
    _zip_dir(kit_dir, zip_path)
    print(f"kit created: {zip_path}")

    if args.checksums:
        # Generate integrity verification files for commercial distribution
        import subprocess
        import sys
        script = os.path.join(root, "tools", "release_checksums.py")
        subprocess.run(
            [sys.executable, script, "--kit", zip_path, "--out", out_root],
            check=True,
            cwd=root,
        )


if __name__ == "__main__":
    main()
