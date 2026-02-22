#!/usr/bin/env python3
"""
Verify SBOM artifact: exists, has table and package entries, optional JSON block.
Exit 0 if valid, non-zero otherwise. Used in CI after generate_sbom.
"""
import json
import os
import re
import sys


def main():
    path = os.environ.get("SBOM_PATH", "SBOM.md")
    if len(sys.argv) > 1:
        path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"verify_sbom: missing file {path}", file=sys.stderr)
        return 1
    with open(path, "r") as f:
        content = f.read()
    if "| Package |" not in content and "| Package | Version |" not in content:
        print("verify_sbom: SBOM must contain package table header", file=sys.stderr)
        return 1
    if "Software Bill of Materials" not in content and "SBOM" not in content:
        print("verify_sbom: SBOM title expected", file=sys.stderr)
        return 1
    # Optional: parse JSON block and check packages list
    m = re.search(r"```json\s*\n(.*?)\n```", content, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if not isinstance(data.get("packages"), list):
                print("verify_sbom: JSON packages list expected", file=sys.stderr)
                return 1
            if len(data["packages"]) == 0:
                print("verify_sbom: at least one package expected", file=sys.stderr)
                return 1
        except json.JSONDecodeError as e:
            print(f"verify_sbom: invalid JSON in SBOM: {e}", file=sys.stderr)
            return 1
    print(f"verify_sbom: OK {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
