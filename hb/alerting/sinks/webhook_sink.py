import json
import urllib.request
from hb.alerting.sinks.base import AlertSink


class WebhookSink(AlertSink):
    def __init__(self, url: str, **kwargs):
        self.url = url

    def emit(self, event):
        data = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"webhook emit failed: {e}")
