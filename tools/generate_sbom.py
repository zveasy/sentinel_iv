#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, timezone


def read_requirements(path):
    deps = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            deps.append(line)
    return deps


def main():
    parser = argparse.ArgumentParser(description="Generate a minimal SBOM from requirements.")
    parser.add_argument("--out", default="SBOM.md")
    parser.add_argument("--requirements", nargs="+", default=["hb/requirements.txt", "hb/requirements-dev.txt"])
    args = parser.parse_args()

    deps = []
    for req in args.requirements:
        if os.path.exists(req):
            deps.extend(read_requirements(req))

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "requirements": args.requirements,
        "dependencies": sorted(set(deps)),
    }

    with open(args.out, "w") as f:
        f.write("# SBOM\\n\\n")
        f.write("Generated: " + payload["generated_utc"] + "\\n\\n")
        f.write("Dependencies:\\n")
        for dep in payload["dependencies"]:
            f.write(f"- {dep}\\n")
        f.write("\\nRaw:\\n\\n```json\\n")
        json.dump(payload, f, indent=2)
        f.write("\\n```\\n")

    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
