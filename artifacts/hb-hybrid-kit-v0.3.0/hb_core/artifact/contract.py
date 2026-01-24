import csv
import json
import os


ARTIFACT_SCHEMA_VERSION = "1.0"


class ArtifactError(ValueError):
    pass


def load_run_meta(artifact_dir):
    path = os.path.join(artifact_dir, "run_meta.json")
    if not os.path.exists(path):
        raise ArtifactError("run_meta.json missing")
    with open(path, "r") as f:
        return json.load(f)


def load_metrics_csv(artifact_dir):
    path = os.path.join(artifact_dir, "metrics.csv")
    if not os.path.exists(path):
        raise ArtifactError("metrics.csv missing")
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
    if not rows:
        raise ArtifactError("metrics.csv is empty")
    return rows


def load_signals_csv(artifact_dir):
    path = os.path.join(artifact_dir, "signals.csv")
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
    return rows


def validate_run_meta(run_meta):
    required = ["program", "subsystem", "test_name"]
    missing = [key for key in required if not run_meta.get(key)]
    if missing:
        raise ArtifactError(f"run_meta.json missing required fields: {', '.join(missing)}")
    version = run_meta.get("schema_version") or ARTIFACT_SCHEMA_VERSION
    return version


def validate_metrics(rows):
    required = {"metric", "value"}
    for row in rows:
        if not required.issubset(row.keys()):
            raise ArtifactError("metrics.csv must include columns: metric,value")
    return True


def validate_artifact_dir(artifact_dir):
    if not os.path.isdir(artifact_dir):
        raise ArtifactError(f"artifact_dir not found: {artifact_dir}")
    run_meta = load_run_meta(artifact_dir)
    metrics = load_metrics_csv(artifact_dir)
    version = validate_run_meta(run_meta)
    validate_metrics(metrics)
    signals_path = os.path.join(artifact_dir, "signals.csv")
    if os.path.exists(signals_path):
        with open(signals_path, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
        if header and "timestamp" not in header and "ts" not in header:
            raise ArtifactError("signals.csv must include timestamp or ts column")
        if header and len(header) < 2:
            raise ArtifactError("signals.csv must include at least one signal column")
    events_path = os.path.join(artifact_dir, "events.jsonl")
    if os.path.exists(events_path):
        with open(events_path, "r") as f:
            first = f.readline().strip()
            if first:
                try:
                    json.loads(first)
                except json.JSONDecodeError as exc:
                    raise ArtifactError(f"events.jsonl invalid: {exc}") from exc
    return {"schema_version": version}
