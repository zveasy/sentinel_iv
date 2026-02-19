#!/usr/bin/env python3
"""
Check that release/customer-facing files do not contain unreplaced placeholders
before shipping. Exit 0 if all placeholders are replaced, 1 otherwise.
Use in CI or pre-release: python tools/check_release_placeholders.py
"""

import os
import sys

# Placeholders that must be replaced before commercial distribution
PLACEHOLDERS = [
    "[YEAR]",
    "[COPYRIGHT HOLDER]",
    "[COPYRIGHT_HOLDER]",
    "[JURISDICTION]",
    "[SUPPORT_EMAIL]",
    "[SUPPORT_PORTAL_URL]",
]

# Files to check (paths relative to repo root)
FILES_TO_CHECK = [
    "release/hb-hybrid-kit/README.md",
    "release/hb-hybrid-kit/LICENSE_COMMERCIAL.txt",
    "docs/SUPPORT.md",
]


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    found = []
    for rel in FILES_TO_CHECK:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, "r", errors="replace") as f:
            text = f.read()
        for placeholder in PLACEHOLDERS:
            if placeholder in text:
                found.append((rel, placeholder))
    if found:
        print("Release placeholders still present (replace before shipping):", file=sys.stderr)
        for rel, placeholder in found:
            print(f"  {rel}: {placeholder}", file=sys.stderr)
        sys.exit(1)
    print("All checked files are free of release placeholders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
