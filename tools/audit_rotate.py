#!/usr/bin/env python3
import argparse
import os
import shutil
from datetime import datetime, timezone

from hb.audit import append_audit_log, file_hash


def rotate_log(log_path, archive_dir):
    os.makedirs(archive_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base = os.path.basename(os.path.dirname(log_path))
    archive_name = f"{base}_audit_{ts}.jsonl"
    archive_path = os.path.join(archive_dir, archive_name)
    shutil.move(log_path, archive_path)
    return archive_path


def iter_audit_logs(reports_dir):
    for root, _, files in os.walk(reports_dir):
        for name in files:
            if name == "audit_log.jsonl":
                yield os.path.join(root, name)


def main():
    parser = argparse.ArgumentParser(description="Rotate audit logs by size")
    parser.add_argument("--reports-dir", default=os.path.join("mvp", "reports"))
    parser.add_argument("--archive-dir", default=os.path.join("logs", "audit"))
    parser.add_argument("--max-bytes", type=int, default=5 * 1024 * 1024)
    args = parser.parse_args()

    rotated = 0
    for log_path in iter_audit_logs(args.reports_dir):
        size = os.path.getsize(log_path)
        if size < args.max_bytes:
            continue
        report_dir = os.path.dirname(log_path)
        archive_path = rotate_log(log_path, args.archive_dir)
        append_audit_log(
            report_dir,
            os.path.basename(report_dir),
            "audit_rotate",
            {
                "archived_path": os.path.abspath(archive_path),
                "archived_sha256": file_hash(archive_path),
                "max_bytes": args.max_bytes,
            },
        )
        rotated += 1

    print(f"rotated {rotated} audit logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
