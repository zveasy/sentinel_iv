import json
from hb.alerting.sinks.base import AlertSink


class StdoutSink(AlertSink):
    def emit(self, event):
        print("HB_ALERT", json.dumps(event))
