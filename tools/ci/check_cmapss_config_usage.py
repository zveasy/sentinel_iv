#!/usr/bin/env python3
import argparse
import os
import sys

import yaml


def main():
    parser = argparse.ArgumentParser(description="CI check to prevent CMAPSS configs in production runs")
    parser.add_argument("--config", required=True)
    parser.add_argument("--allow-regression", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"config not found: {args.config}", file=sys.stderr)
        return 2

    with open(args.config, "r") as f:
        payload = yaml.safe_load(f) or {}

    purpose = str(payload.get("purpose", "")).lower()
    variant = str(payload.get("variant", "")).lower()

    if "regression_calibration_only" in purpose or variant.startswith("fd"):
        if not args.allow_regression:
            print(
                "CI policy violation: CMAPSS regression config used without --allow-regression",
                file=sys.stderr,
            )
            return 1
    print("CMAPSS config check ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
