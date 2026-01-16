#!/usr/bin/env python3
import argparse
import sys
import yaml


def main():
    parser = argparse.ArgumentParser(description="CI check for baseline governance policy")
    parser.add_argument("--policy", default="baseline_policy.yaml")
    args = parser.parse_args()

    with open(args.policy, "r") as f:
        payload = yaml.safe_load(f)
    policy = payload.get("baseline_policy", payload)
    governance = policy.get("governance", {})
    require_approval = governance.get("require_approval")
    approvals_required = int(governance.get("approvals_required", 0))

    if not require_approval:
        print("baseline policy check failed: governance.require_approval must be true in CI")
        return 1
    if approvals_required < 1:
        print("baseline policy check failed: approvals_required must be >= 1")
        return 1
    print("baseline policy check ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
