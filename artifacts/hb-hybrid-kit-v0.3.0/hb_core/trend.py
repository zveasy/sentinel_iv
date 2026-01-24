import json
import os


def read_plan_history(history_path, limit=50):
    if not os.path.exists(history_path):
        return []
    rows = []
    with open(history_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def build_trend(history_rows, scenario_id):
    series = []
    for row in history_rows:
        if row.get("scenario_id") != scenario_id:
            continue
        series.append(
            {
                "ts_utc": row.get("ts_utc"),
                "status": row.get("status"),
                "drift_score": row.get("drift_score"),
            }
        )
    return series
