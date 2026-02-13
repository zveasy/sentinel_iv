#!/usr/bin/env python3
"""Generate checksum files for a release kit zip (and optionally other artifacts)."""

import argparse
import hashlib
import os


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Generate release checksums for integrity verification.")
    parser.add_argument("--kit", required=True, help="Path to the kit zip file (e.g. artifacts/hb-hybrid-kit-v0.3.0.zip)")
    parser.add_argument("--out", default="artifacts", help="Directory to write checksums.txt and .sha256 file")
    args = parser.parse_args()

    kit_path = os.path.abspath(args.kit)
    if not os.path.isfile(kit_path):
        raise FileNotFoundError(f"Kit file not found: {kit_path}")

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    digest = sha256_file(kit_path)
    base = os.path.basename(kit_path)

    # Single-line .sha256 file (format: digest  filename)
    sha256_filepath = os.path.join(out_dir, base + ".sha256")
    with open(sha256_filepath, "w") as f:
        f.write(f"{digest}  {base}\n")
    print(f"Wrote {sha256_filepath}")

    # checksums.txt with optional header for multiple files
    checksums_path = os.path.join(out_dir, "checksums.txt")
    with open(checksums_path, "w") as f:
        f.write(f"SHA256 ({base}) = {digest}\n")
    print(f"Wrote {checksums_path}")


if __name__ == "__main__":
    main()
