import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


def default_hb_home():
    return os.environ.get("HB_HOME", os.path.join(os.path.expanduser("~"), ".hb"))


def default_log_path():
    return os.path.join(default_hb_home(), "feedback", "feedback_log.jsonl")


def _ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_feedback_payload(path):
    with open(path, "r") as f:
        return json.load(f)


def write_feedback_record(payload, log_path=None):
    log_path = log_path or default_log_path()
    _ensure_dir(log_path)
    with open(log_path, "a") as f:
        f.write(json.dumps(payload) + "\n")


def export_feedback(log_path, output_path=None, mode="summary"):
    log_path = log_path or default_log_path()
    if mode not in {"summary", "raw"}:
        raise ValueError("invalid export mode")
    action_weights = {
        "correct": 1.0,
        "too_sensitive": 0.5,
        "missed_severity": 0.0,
        "unknown": 0.0,
    }
    records = []
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    weighted_sum = 0.0
    weighted_count = 0
    for record in records:
        action = (record.get("operator_action") or "unknown").strip().lower().replace(" ", "_")
        weight = action_weights.get(action, 0.0)
        weighted_sum += weight
        weighted_count += 1
    health_score = round((weighted_sum / weighted_count) * 100, 2) if weighted_count else 0.0
    if mode == "raw":
        raw_records = []
        for record in records:
            action = (record.get("operator_action") or "unknown").strip().lower().replace(" ", "_")
            weight = action_weights.get(action, 0.0)
            record_with_score = dict(record)
            record_with_score["health_score"] = round(weight * 100, 2)
            raw_records.append(record_with_score)
        payload = {"records": raw_records, "count": len(raw_records), "health_score": health_score}
    else:
        counts = {}
        actions = {}
        for record in records:
            metric = record.get("metric") or "unknown"
            counts[metric] = counts.get(metric, 0) + 1
            action = record.get("operator_action") or "unknown"
            actions[action] = actions.get(action, 0) + 1
        payload = {
            "count": len(records),
            "by_metric": counts,
            "by_action": actions,
            "health_score": health_score,
        }
    if output_path:
        _ensure_dir(output_path)
        with open(output_path, "w") as f:
            json.dump(payload, f, indent=2)
    return payload


class FeedbackHandler(BaseHTTPRequestHandler):
    log_path = None

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._set_headers(200)
            self.wfile.write(b'{"status":"ok"}')
            return
        if parsed.path == "/count":
            count = 0
            if self.log_path and os.path.exists(self.log_path):
                with open(self.log_path, "r") as f:
                    for line in f:
                        if line.strip():
                            count += 1
            self._set_headers(200)
            self.wfile.write(json.dumps({"count": count}).encode("utf-8"))
            return
        if parsed.path == "/export":
            query = parse_qs(parsed.query or "")
            mode = (query.get("mode") or ["summary"])[0]
            try:
                payload = export_feedback(self.log_path, None, mode=mode)
            except ValueError as exc:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
                return
            self._set_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>HB Feedback Hub</title>
  <style>
    :root {
      --bg: #f5f2ec;
      --panel: #ffffff;
      --ink: #1f2a33;
      --muted: #5c6b76;
      --accent: #0e6f8a;
      --accent-2: #d9822b;
      --ok: #2f855a;
      --warn: #b45309;
      --shadow: 0 12px 30px rgba(24, 39, 75, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Trebuchet MS", "Gill Sans", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at top left, #fdf8f0, var(--bg));
    }
    header {
      padding: 32px 40px 16px;
      background: linear-gradient(120deg, #f7efe2 0%, #f3f7f9 100%);
      border-bottom: 1px solid #e6e2d7;
    }
    header h1 {
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0.2px;
    }
    header p {
      margin: 0;
      color: var(--muted);
      font-size: 15px;
    }
    main {
      padding: 28px 40px 40px;
      display: grid;
      gap: 20px;
    }
    .grid {
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }
    .card {
      background: var(--panel);
      border-radius: 14px;
      padding: 18px 20px;
      box-shadow: var(--shadow);
      border: 1px solid #edf0f3;
    }
    .label {
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 1px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .big {
      font-size: 28px;
      font-weight: 600;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    button {
      border: none;
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12); }
    .primary { background: var(--accent); color: #fff; }
    .secondary { background: #eef4f6; color: var(--ink); }
    .warn { background: var(--accent-2); color: #fff; }
    .status {
      color: var(--muted);
      font-size: 14px;
      margin-top: 6px;
    }
    .steps ol {
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.6;
    }
    code {
      background: #f2f2f2;
      padding: 2px 6px;
      border-radius: 6px;
      font-family: "Courier New", monospace;
      font-size: 13px;
    }
    @media (max-width: 640px) {
      header, main { padding: 22px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>HB Feedback Hub</h1>
    <p>Privacy-safe feedback, stored locally. No raw data ever leaves this machine.</p>
  </header>
  <main>
    <div class="grid">
      <div class="card">
        <div class="label">Records Received</div>
        <div class="big" id="count">--</div>
        <div class="status" id="count-status">Checking local log...</div>
      </div>
      <div class="card">
        <div class="label">Server Status</div>
        <div class="big" id="health">OK</div>
        <div class="status">Endpoint: <code>/feedback</code></div>
      </div>
      <div class="card">
        <div class="label">Log Location</div>
        <div class="status"><code>~/.hb/feedback/feedback_log.jsonl</code></div>
        <div class="status">Override with <code>HB_HOME</code>.</div>
      </div>
    </div>

    <div class="card">
      <div class="label">Quick Actions</div>
      <div class="actions">
        <button class="primary" onclick="downloadExport('summary')">Download Summary</button>
        <button class="secondary" onclick="downloadExport('raw')">Download Raw Records</button>
        <button class="warn" onclick="refreshCount()">Refresh Count</button>
      </div>
      <div class="status" id="export-status"></div>
    </div>

    <div class="card steps">
      <div class="label">How To Collect Feedback</div>
      <ol>
        <li>Open a drift report HTML file.</li>
        <li>Enable feedback sending.</li>
        <li>Click Correct / Too Sensitive / Missed Severity.</li>
        <li>Return here to download a summary.</li>
      </ol>
    </div>
  </main>

  <script>
    function refreshCount() {
      fetch('/count').then(r => r.json()).then(data => {
        document.getElementById('count').textContent = data.count;
        document.getElementById('count-status').textContent = 'Updated just now.';
      }).catch(() => {
        document.getElementById('count-status').textContent = 'Unable to reach count endpoint.';
      });
    }
    function downloadExport(mode) {
      fetch('/export?mode=' + mode).then(r => r.json()).then(data => {
        const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = mode === 'raw' ? 'hb_feedback_raw.json' : 'hb_feedback_summary.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        document.getElementById('export-status').textContent = 'Download ready.';
      }).catch(() => {
        document.getElementById('export-status').textContent = 'Export failed. Is the server running?';
      });
    }
    refreshCount();
  </script>
</body>
</html>
"""
            self.wfile.write(html.encode("utf-8"))
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self._set_headers(404)
        self.wfile.write(b'{"error":"not_found"}')

    def do_POST(self):
        if self.path != "/feedback":
            self._set_headers(404)
            self.wfile.write(b'{"error":"not_found"}')
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(b'{"error":"invalid_json"}')
            return
        write_feedback_record(payload, log_path=self.log_path)
        self._set_headers(200)
        self.wfile.write(b'{"status":"saved"}')


def serve_feedback(port=8765, log_path=None):
    log_path = log_path or default_log_path()
    handler = FeedbackHandler
    handler.log_path = log_path
    server = HTTPServer(("127.0.0.1", int(port)), handler)
    print(f"feedback server listening on http://127.0.0.1:{port}")
    server.serve_forever()
