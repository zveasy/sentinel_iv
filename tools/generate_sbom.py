#!/usr/bin/env python3
"""
Generate a Software Bill of Materials (SBOM) from requirements files.
Outputs SBOM.md with package names, versions (from pinned requirements or pip list), and machine-readable JSON.
Run from repo root. For versions from installed env: run from a venv with deps installed and use --from-installed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone


# Match package name and optional version: package, package==x.y.z, package>=x, etc.
REQ_SPEC = re.compile(r"^([a-zA-Z0-9][a-zA-Z0-9._-]*)\s*(?:==|>=|<=|~=)?\s*([^\s#]+)?")


def read_requirements(path):
    """Return list of (name, version_or_none) from a requirements file."""
    deps = []
    for line in open(path, "r"):
        line = line.strip().split("#")[0].strip()
        if not line:
            continue
        m = REQ_SPEC.match(line)
        if m:
            name = m.group(1).strip()
            version = m.group(2).strip() if m.group(2) else None
            deps.append((name, version))
    return deps


def get_installed_versions():
    """Return dict of package_name -> version from current env (pip list --format=json)."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout)
        return {str(p.get("name", "")).lower(): str(p.get("version", "")) for p in data}
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="Generate a minimal SBOM from requirements (with versions when available)."
    )
    parser.add_argument("--out", default="SBOM.md", help="Output path for SBOM markdown")
    parser.add_argument(
        "--requirements",
        nargs="+",
        default=["hb/requirements.txt", "hb/requirements-dev.txt"],
        help="Requirements files to include",
    )
    parser.add_argument(
        "--from-installed",
        action="store_true",
        help="Resolve versions from current env (pip list); use when run inside venv with deps installed",
    )
    args = parser.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root)

    # Collect (name, version) from requirements; normalize name to lowercase for matching
    seen = set()
    deps = []
    for req_path in args.requirements:
        if not os.path.exists(req_path):
            continue
        for name, version in read_requirements(req_path):
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            deps.append((name, version))

    installed = get_installed_versions() if args.from_installed else {}

    # Prefer version from requirements; if missing and --from-installed, use installed
    rows = []
    for name, version in sorted(deps, key=lambda x: x[0].lower()):
        if not version and args.from_installed:
            version = installed.get(name.lower()) or ""
        rows.append({"name": name, "version": version or "(not pinned)"})

    generated_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_utc": generated_utc,
        "requirements": args.requirements,
        "from_installed": args.from_installed,
        "packages": rows,
    }

    with open(args.out, "w") as f:
        f.write("# Software Bill of Materials (SBOM)\n\n")
        f.write(f"**Generated:** {generated_utc}\n\n")
        f.write("| Package | Version |\n")
        f.write("|---------|--------|\n")
        for r in rows:
            v = r["version"] or "—"
            f.write(f"| {r['name']} | {v} |\n")
        f.write("\n## Source\n\n")
        f.write("Requirements files used:\n")
        for p in args.requirements:
            f.write(f"- `{p}`\n")
        if args.from_installed:
            f.write("\nVersions were resolved from the current Python environment (`pip list`).\n")
        else:
            f.write("\nVersions are from pinned requirements. For installed versions, run from a venv with deps installed and use `--from-installed`.\n")
        f.write("\n## Machine-readable (JSON)\n\n```json\n")
        json.dump(payload, f, indent=2)
        f.write("\n```\n")

    print(f"Wrote {args.out} ({len(rows)} packages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
