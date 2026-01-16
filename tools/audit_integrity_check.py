#!/usr/bin/env python3
import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from hb.audit import verify_audit_log


def iter_audit_logs(reports_dir):
    for root, _, files in os.walk(reports_dir):
        for name in files:
            if name == "audit_log.jsonl":
                yield os.path.join(root, name)


def main():
    parser = argparse.ArgumentParser(description="Audit log integrity checks")
    parser.add_argument("--reports-dir", default=os.path.join("mvp", "reports"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    logs = list(iter_audit_logs(args.reports_dir))
    if not logs:
        print("no audit logs found")
        return 0

    failed = 0
    for log_path in logs:
        issues = verify_audit_log(log_path, strict=args.strict)
        if issues:
            failed += 1
            print(f"FAIL {log_path}: {issues[0]}")
        else:
            print(f"OK {log_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
