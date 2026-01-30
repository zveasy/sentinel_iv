#!/usr/bin/env python3
import argparse
import json
import sys
import yaml


def _load_guardrails(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f) or {}
    return payload.get("guardrails", {})


def _parse_time_window(window):
    start, end = window.split("-", 1)
    return start.strip(), end.strip()


def _check_time_window(allowed, window):
    if not window:
        return True
    for item in allowed or []:
        start, end = _parse_time_window(item)
        if start <= window <= end:
            return True
    return False


def _check_action(guardrails, action):
    issues = []
    action_type = (action.get("action_type") or "").lower()
    params = action.get("params") or {}
    ttl = action.get("ttl_seconds")
    if ttl is not None:
        ttl_max = guardrails.get("ttl_seconds_max")
        if ttl_max is not None and ttl > ttl_max:
            issues.append(f"ttl_seconds {ttl} exceeds max {ttl_max}")
    window = action.get("window_utc")
    if window and not _check_time_window(guardrails.get("allowed_windows_utc"), window):
        issues.append(f"window_utc {window} not in allowed_windows_utc")

    actions = guardrails.get("actions") or {}
    if action_type == "safe_mode":
        allowed = actions.get("safe_mode", {}).get("allowed_levels") or []
        level = params.get("level")
        if allowed and level not in allowed:
            issues.append(f"safe_mode level {level} not allowed")
    elif action_type == "rate_limit":
        min_rps = actions.get("rate_limit", {}).get("min_rps")
        max_rps = actions.get("rate_limit", {}).get("max_rps")
        rps = params.get("rps")
        if rps is None:
            issues.append("rate_limit missing params.rps")
        else:
            if min_rps is not None and rps < min_rps:
                issues.append(f"rps {rps} below min {min_rps}")
            if max_rps is not None and rps > max_rps:
                issues.append(f"rps {rps} above max {max_rps}")
    elif action_type == "restart":
        max_per_hour = actions.get("restart", {}).get("max_per_hour")
        count = params.get("count", 1)
        if max_per_hour is not None and count > max_per_hour:
            issues.append(f"restart count {count} exceeds max_per_hour {max_per_hour}")
    else:
        issues.append(f"unsupported action_type {action_type}")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate actions against guardrails")
    parser.add_argument("--config", default="configs/guardrails.yaml")
    parser.add_argument("--action", required=True, help="path to action JSON")
    args = parser.parse_args()

    guardrails = _load_guardrails(args.config)
    with open(args.action, "r") as f:
        action = json.load(f)

    issues = _check_action(guardrails, action)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        sys.exit(1)
    print("PASS: action within guardrails")
    sys.exit(0)


if __name__ == "__main__":
    main()
