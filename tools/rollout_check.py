#!/usr/bin/env python3
import argparse
import os
import sys
import yaml


def _load_gates(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f) or {}
    return payload.get("gates", [])


def _check_gate(gate):
    gate_type = gate.get("type")
    name = gate.get("name", "gate")
    if gate_type == "file_exists":
        path = gate.get("path")
        if not path or not os.path.exists(path):
            return False, f"{name}: missing {path}"
        return True, f"{name}: ok"
    return False, f"{name}: unsupported gate type {gate_type}"


def main():
    parser = argparse.ArgumentParser(description="Run rollout gates checks")
    parser.add_argument("--config", default="configs/rollout_gates.yaml")
    args = parser.parse_args()

    gates = _load_gates(args.config)
    if not gates:
        print("FAIL: no gates defined")
        sys.exit(1)
    issues = []
    for gate in gates:
        ok, message = _check_gate(gate)
        print(message)
        if not ok:
            issues.append(message)
    if issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
