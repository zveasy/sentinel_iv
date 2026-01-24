import json
import time


class PerfRecorder:
    def __init__(self):
        self.spans = []
        self.meta = {}
        self._seen = set()

    def add_meta(self, **kwargs):
        for key, value in kwargs.items():
            if value is None or key in self._seen:
                continue
            self.meta[key] = value
            self._seen.add(key)

    def span(self, name):
        return _PerfSpan(self, name)

    def write(self, path):
        payload = {
            "meta": self.meta,
            "spans": self.spans,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)


class _PerfSpan:
    def __init__(self, recorder, name):
        self.recorder = recorder
        self.name = name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc, tb):
        end = time.time()
        self.recorder.spans.append(
            {
                "name": self.name,
                "start_s": self.start,
                "duration_s": round(end - self.start, 6),
            }
        )
