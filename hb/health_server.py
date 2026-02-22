"""
Health HTTP server: /ready, /live, /metrics for observability.
"""
import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable

from hb.metrics_prometheus import render_prometheus, write_metrics_file


def _check_db(path: str) -> tuple[bool, str]:
    if not path or not os.path.isfile(path):
        return False, "db_not_configured"
    try:
        import sqlite3
        conn = sqlite3.connect(path, timeout=2)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return True, "ok"
    except Exception as e:
        return False, str(e).replace("\n", " ")[:200]


def _check_config(path: str) -> tuple[bool, str]:
    if not path or not os.path.isfile(path):
        return True, "ok"  # no config required
    try:
        with open(path, "r") as f:
            f.read(4096)
        return True, "ok"
    except Exception as e:
        return False, str(e).replace("\n", " ")[:200]


def serve(bind: str, port: int, db_path: str | None = None, config_path: str | None = None,
          metrics_file_path: str | None = None, metrics_interval_sec: float = 15.0):
    ready_checks = []
    if db_path:
        ready_checks.append(("db", lambda: _check_db(db_path)))
    if config_path:
        ready_checks.append(("config", lambda: _check_config(config_path)))

    def _ready_ok() -> bool:
        for _, fn in ready_checks:
            ok, _ = fn()
            if not ok:
                return False
        return True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # quiet by default

        def do_GET(self):
            if self.path == "/live":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"up"}\n')
                return
            if self.path == "/ready":
                ok = _ready_ok()
                status = 200 if ok else 503
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = {"ready": ok}
                if not ok and ready_checks:
                    details = {}
                    for name, fn in ready_checks:
                        cok, msg = fn()
                        details[name] = "ok" if cok else msg
                    payload["checks"] = details
                self.wfile.write(json.dumps(payload).encode("utf-8") + b"\n")
                return
            if self.path == "/metrics":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(render_prometheus().encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

    server = HTTPServer((bind, port), Handler)

    def write_metrics_loop():
        while True:
            time.sleep(metrics_interval_sec)
            if metrics_file_path:
                write_metrics_file(metrics_file_path)

    if metrics_file_path:
        t = threading.Thread(target=write_metrics_loop, daemon=True)
        t.start()

    server.serve_forever()
