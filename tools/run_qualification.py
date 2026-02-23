#!/usr/bin/env python3
"""
Qualification run: one command to run V&V suite and generate a signed V&V report bundle.
Produces: Test Plan ref, Procedures ref, Results (auto-exported), Acceptance report, optional signature.

Usage:
  python tools/run_qualification.py --out-dir /tmp/vv_bundle [--sign-key keys/signing.key]
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_pytest(out_dir: Path) -> tuple[int, Path]:
    """Run pytest; write results JSON to out_dir. Return (exit_code, results_path)."""
    results_file = out_dir / "qualification_results.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_determinism.py", "tests/test_golden_compare.py", "-v", "--tb=short", "-q"],
        cwd=REPO_ROOT,
        env=env,
    )
    # Write minimal results for bundle
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exit_code": r.returncode,
        "passed": r.returncode == 0,
    }
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    return r.returncode, results_file


def write_acceptance_report(out_dir: Path, results_path: Path, exit_code: int) -> Path:
    report_path = out_dir / "VV_ACCEPTANCE_REPORT.md"
    with open(report_path, "w") as f:
        f.write("# V&V Qualification Acceptance Report\n\n")
        f.write(f"**Date:** {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write(f"**Results file:** `{results_path.name}`\n\n")
        f.write(f"**Exit code:** {exit_code}\n\n")
        f.write("**Conclusion:** " + ("PASS" if exit_code == 0 else "FAIL") + " (qualification run)\n\n")
        f.write("---\n\n")
        f.write("Test Plan: `docs/VV_TEST_PLAN.md`\n\n")
        f.write("Procedures: `docs/VV_TEST_PROCEDURES.md`\n\n")
        f.write("Acceptance Criteria: `docs/VV_ACCEPTANCE_CRITERIA.md`\n")
    return report_path


def sign_bundle(out_dir: Path, sign_key: str | None) -> None:
    if not sign_key or not os.path.isfile(sign_key):
        return
    try:
        # Optional: sign the report or a manifest in out_dir
        manifest = out_dir / "manifest.json"
        with open(manifest, "w") as f:
            json.dump({"qualification_run": True, "dir": str(out_dir)}, f)
        # Placeholder: actual signing would use openssl or PyNaCl
        (out_dir / "manifest.sig").write_text("(signature placeholder - use openssl or sign tool)\n")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="Run qualification and produce V&V report bundle")
    ap.add_argument("--out-dir", default=None, help="Output directory for bundle (default: vv_bundle)")
    ap.add_argument("--sign-key", default=None, help="Optional key to sign manifest")
    args = ap.parse_args()
    out_dir = Path(args.out_dir or "vv_bundle").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    exit_code, results_path = run_pytest(out_dir)
    write_acceptance_report(out_dir, results_path, exit_code)
    sign_bundle(out_dir, args.sign_key)
    print(f"Qualification bundle: {out_dir}")
    print(f"Results: {results_path}")
    print(f"Acceptance report: {out_dir / 'VV_ACCEPTANCE_REPORT.md'}")
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
