import csv
import json


class Welford:
    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.min = None
        self.max = None

    def update(self, value):
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        if self.min is None or value < self.min:
            self.min = value
        if self.max is None or value > self.max:
            self.max = value

    def summary(self):
        variance = self.m2 / self.count if self.count else 0.0
        std = variance ** 0.5
        return {
            "count": self.count,
            "mean": self.mean if self.count else None,
            "variance": variance if self.count else None,
            "std": std if self.count else None,
            "min": self.min,
            "max": self.max,
        }


def aggregate_csv(path, metric_col="metric", value_col="value"):
    stats = {}
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metric = row.get(metric_col)
            value = row.get(value_col)
            if not metric or value in (None, ""):
                continue
            try:
                value = float(value)
            except ValueError:
                continue
            agg = stats.get(metric)
            if agg is None:
                agg = Welford()
                stats[metric] = agg
            agg.update(value)
    return {metric: agg.summary() for metric, agg in stats.items()}


def aggregate_jsonl(path, metric_key="metric", value_key="value"):
    stats = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            metric = payload.get(metric_key)
            value = payload.get(value_key)
            if not metric or value in (None, ""):
                continue
            try:
                value = float(value)
            except ValueError:
                continue
            agg = stats.get(metric)
            if agg is None:
                agg = Welford()
                stats[metric] = agg
            agg.update(value)
    return {metric: agg.summary() for metric, agg in stats.items()}
