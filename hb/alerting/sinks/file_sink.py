import json
import os
from hb.alerting.sinks.base import AlertSink


class FileSink(AlertSink):
    def __init__(self, path: str = "alerts.jsonl", **kwargs):
        self.path = path

    def emit(self, event):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")
