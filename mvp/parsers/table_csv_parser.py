import csv

from mvp import analyze


def parse(path):
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise analyze.ParseError("CSV missing header row")
        rows = list(reader)
        if not rows:
            raise analyze.ParseError("CSV contains no data rows")
        row = rows[0]
        metrics = {}
        for key, value in row.items():
            if key is None:
                continue
            name = key.strip()
            if name == "":
                continue
            metrics[name] = analyze.parse_value(value)
        return metrics
