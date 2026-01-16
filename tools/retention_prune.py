#!/usr/bin/env python3
import argparse
import os
import shutil
from datetime import datetime, timezone, timedelta

import yaml

from hb.registry import init_db


def load_policy(path):
    with open(path, "r") as f:
        return yaml.safe_load(f).get("retention", {})


def main():
    parser = argparse.ArgumentParser(description="Prune old reports and registry entries.")
    parser.add_argument("--policy", default="retention_policy.yaml")
    parser.add_argument("--db", default="runs.db")
    args = parser.parse_args()

    policy = load_policy(args.policy)
    keep_latest = policy.get("keep_latest", 200)
    max_age_days = policy.get("max_age_days", 90)
    reports_dir = policy.get("reports_dir", "mvp/reports")

    conn = init_db(args.db)
    cursor = conn.execute(
        "SELECT run_id, created_at FROM runs ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    keep_ids = {run_id for run_id, _ in rows[:keep_latest]}
    removed = 0
    for run_id, created_at in rows:
        if run_id in keep_ids:
            continue
        if created_at:
            try:
                ts = datetime.fromisoformat(created_at)
            except ValueError:
                ts = None
        else:
            ts = None
        if ts and ts > cutoff:
            continue
        report_path = os.path.join(reports_dir, run_id)
        if os.path.isdir(report_path):
            shutil.rmtree(report_path)
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM metrics WHERE run_id = ?", (run_id,))
        removed += 1
    conn.commit()

    print(f"pruned {removed} runs")


if __name__ == "__main__":
    main()
