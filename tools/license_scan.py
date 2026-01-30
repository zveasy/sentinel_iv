#!/usr/bin/env python3
import argparse
import csv
import json
from importlib import metadata


def _license_from_metadata(dist):
    meta = dist.metadata
    license_text = (meta.get("License") or "").strip()
    if license_text:
        return license_text
    classifiers = meta.get_all("Classifier") or []
    licenses = [c.split("::")[-1].strip() for c in classifiers if "License ::" in c]
    return ", ".join(sorted(set(licenses))) if licenses else "UNKNOWN"


def scan_licenses():
    results = []
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or dist.metadata.get("Summary") or dist.metadata.get("name")
        version = dist.version or ""
        license_text = _license_from_metadata(dist)
        results.append({"name": name or "UNKNOWN", "version": version, "license": license_text})
    results.sort(key=lambda item: item["name"].lower())
    return results


def main():
    parser = argparse.ArgumentParser(description="Scan installed Python package licenses")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()

    results = scan_licenses()
    if args.format == "json":
        with open(args.out, "w") as f:
            json.dump({"count": len(results), "packages": results}, f, indent=2)
    else:
        with open(args.out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "version", "license"])
            for row in results:
                writer.writerow([row["name"], row["version"], row["license"]])

    print(f"wrote {len(results)} records to {args.out}")


if __name__ == "__main__":
    main()
