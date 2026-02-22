#!/usr/bin/env python3
"""
Validate metric_registry.yaml: version field, required structure, and optional invariant coverage.
Use in CI to guard config changes. Exit 0 if valid, 1 otherwise.
"""
import argparse
import os
import sys

import yaml


def main():
    p = argparse.ArgumentParser(description="Validate metric_registry.yaml")
    p.add_argument("--config", default="metric_registry.yaml")
    p.add_argument("--require-version", action="store_true", help="Require a version field")
    p.add_argument("--require-invariants", action="store_true", help="Warn if no invariant rules for critical metrics")
    args = p.parse_args()
    path = args.config
    if not os.path.isfile(path):
        print(f"Config not found: {path}", file=sys.stderr)
        return 1
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    metrics = data.get("metrics") or {}
    if args.require_version and not data.get("version"):
        print("metric_registry must have a 'version' field", file=sys.stderr)
        return 1
    errors = []
    for name, cfg in metrics.items():
        if not isinstance(cfg, dict):
            errors.append(f"metric {name}: must be a mapping")
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    if args.require_invariants:
        critical = [m for m, cfg in metrics.items() if cfg.get("critical")]
        no_inv = [m for m in critical if not any(k in metrics[m] for k in ("invariant_eq", "invariant_max", "invariant_min"))]
        if no_inv:
            print(f"Warning: critical metrics without invariant rules: {no_inv}", file=sys.stderr)
    print("Valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
