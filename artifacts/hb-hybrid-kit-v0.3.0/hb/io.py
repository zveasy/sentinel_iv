import csv
import json
import os


def read_json(path):
    with open(path, "r") as f:
        return json.load(f)


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def read_metrics_csv(path):
    metrics = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metrics.append(row)
    return metrics


def write_metrics_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        fieldnames = ["metric", "value", "unit", "tags"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
