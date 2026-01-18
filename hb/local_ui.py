import argparse
import json
import os
import shutil
import subprocess
import uuid
import time
import zipfile
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from hb import cli
from hb import watch


def _default_workspace():
    return os.environ.get("HB_WORKSPACE", os.path.join(os.path.expanduser("~"), ".harmony_bridge"))


def _ensure_dirs(workspace):
    paths = [
        os.path.join(workspace, "baselines"),
        os.path.join(workspace, "runs"),
        os.path.join(workspace, "reports"),
        os.path.join(workspace, "logs"),
        os.path.join(workspace, "feedback"),
    ]
    for path in paths:
        os.makedirs(path, exist_ok=True)


def _save_upload_bytes(data, filename, dest_dir, prefix):
    filename = os.path.basename(filename)
    ext = os.path.splitext(filename)[1]
    out_name = f"{prefix}_{uuid.uuid4().hex}{ext}"
    out_path = os.path.join(dest_dir, out_name)
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path


def _parse_multipart(headers, body):
    content_type = headers.get("Content-Type")
    if not content_type:
        return {}, {}
    message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body
    parsed = BytesParser(policy=default).parsebytes(message)
    form = {}
    files = {}
    for part in parsed.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="Content-Disposition")
        filename = part.get_param("filename", header="Content-Disposition")
        payload = part.get_payload(decode=True)
        if filename:
            files[name] = {"filename": filename, "data": payload or b""}
        else:
            text = payload.decode(part.get_content_charset() or "utf-8") if payload else ""
            form[name] = text
    return form, files


def _open_report(path):
    if shutil.which("open"):
        subprocess.run(["open", path], check=False)
    elif shutil.which("xdg-open"):
        subprocess.run(["xdg-open", path], check=False)


def _support_bundle(report_dir, out_dir):
    bundle_name = f"support_bundle_{os.path.basename(report_dir)}.zip"
    bundle_path = os.path.join(out_dir, bundle_name)
    files = [
        os.path.join(report_dir, "drift_report.json"),
        os.path.join(report_dir, "drift_report.html"),
        os.path.join(report_dir, "artifact_manifest.json"),
        os.path.join(report_dir, "audit_log.jsonl"),
    ]
    manifest_path = os.path.join(out_dir, f"support_manifest_{os.path.basename(report_dir)}.json")
    manifest = {"files": [path for path in files if os.path.exists(path)]}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in manifest["files"]:
            zf.write(path, os.path.join(os.path.basename(report_dir), os.path.basename(path)))
        zf.write(manifest_path, os.path.basename(manifest_path))
    return bundle_path


class LocalUIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _render(self, body, status=200):
        self._set_headers(status)
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._set_headers(200, "application/json")
            self.wfile.write(b'{"status":"ok"}')
            return
        if parsed.path == "/download":
            query = parse_qs(parsed.query or "")
            file_path = (query.get("file") or [None])[0]
            if not file_path or not os.path.exists(file_path):
                self._set_headers(404, "application/json")
                self.wfile.write(b'{"error":"not_found"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"')
            self.end_headers()
            with open(file_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return
        if parsed.path in ("/", "/index.html"):
            self._render(self._page())
            return
        if parsed.path == "/watch/status":
            self._set_headers(200, "application/json")
            running = bool(getattr(self.server, "watch_active", False))
            payload = {"active": running}
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        self._set_headers(404, "application/json")
        self.wfile.write(b'{"error":"not_found"}')

    def do_POST(self):
        if self.path == "/watch/start":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            form, _ = _parse_multipart(self.headers, body)
            workspace = form.get("workspace") or _default_workspace()
            _ensure_dirs(workspace)
            watch_dir = form.get("watch_dir")
            source = form.get("source") or "pba_excel"
            pattern = form.get("pattern") or "*"
            interval = int(form.get("interval") or 604800)
            if not watch_dir:
                self._set_headers(400, "application/json")
                self.wfile.write(b'{"error":"missing_watch_dir"}')
                return
            if not os.path.isdir(watch_dir):
                self._set_headers(400, "application/json")
                self.wfile.write(b'{"error":"watch_dir_not_found"}')
                return
            if getattr(self.server, "watch_active", False):
                self._set_headers(200, "application/json")
                self.wfile.write(b'{"status":"already_running"}')
                return
            self.server.watch_active = True
            self.server.watch_config = {
                "watch_dir": watch_dir,
                "source": source,
                "pattern": pattern,
                "interval": interval,
                "workspace": workspace,
            }
            self._set_headers(200, "application/json")
            self.wfile.write(b'{"status":"started"}')
            return
        if self.path == "/watch/stop":
            if getattr(self.server, "watch_active", False):
                self.server.watch_active = False
                self._set_headers(200, "application/json")
                self.wfile.write(b'{"status":"stopped"}')
            else:
                self._set_headers(200, "application/json")
                self.wfile.write(b'{"status":"not_running"}')
            return
        if self.path != "/run":
            self._set_headers(404, "application/json")
            self.wfile.write(b'{"error":"not_found"}')
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        form, files = _parse_multipart(self.headers, body)
        workspace = form.get("workspace") or _default_workspace()
        _ensure_dirs(workspace)
        mode = form.get("mode") or "current"
        source = form.get("source") or "pba_excel"
        run_meta_field = files.get("run_meta")
        data_field = files.get("data_file")

        if not data_field or not data_field.get("filename"):
            self._render(self._page(error="Please upload a data file."), status=400)
            return

        dest_dir = os.path.join(workspace, "baselines" if mode == "baseline" else "runs")
        data_path = _save_upload_bytes(data_field["data"], data_field["filename"], dest_dir, mode)
        run_meta_path = None
        if run_meta_field and run_meta_field.get("filename"):
            run_meta_path = _save_upload_bytes(
                run_meta_field["data"], run_meta_field["filename"], os.path.join(workspace, "logs"), "run_meta"
            )

        reports_dir = os.path.join(workspace, "reports")
        db_path = os.path.join(workspace, "logs", "runs.db")

        args = argparse.Namespace(
            source=source,
            path=data_path,
            run_meta=run_meta_path,
            out=None,
            stream=False,
            baseline_policy=os.environ.get("HB_BASELINE_POLICY", "baseline_policy.yaml"),
            metric_registry=os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml"),
            db=db_path,
            reports=reports_dir,
            top=5,
            pdf=False,
            encrypt_key=None,
            sign_key=None,
            redaction_policy=None,
        )

        try:
            report_dir = cli.run(args)
        except Exception as exc:
            message = str(exc)
            if "schema error" in message.lower() or "schema_error" in message.lower():
                message = f"Schema mismatch: {message}"
            self._render(self._page(error=message), status=400)
            return

        report_path = os.path.join(report_dir, "drift_report.html")
        _open_report(report_path)
        bundle_path = _support_bundle(report_dir, os.path.join(workspace, "logs"))
        link = f"file://{report_path}"
        self._render(
            self._page(
                success=f"Report generated: {report_path}",
                report_link=link,
                bundle_link=f"/download?file={bundle_path}",
            )
        )

    def _page(self, error=None, success=None, report_link=None, bundle_link=None):
        workspace = _default_workspace()
        sources = [
            ("pba_excel", "PBA Excel/CSV"),
            ("nasa_http_tsv", "NASA HTTP TSV"),
            ("cmapss_fd001", "CMAPSS FD001"),
            ("cmapss_fd002", "CMAPSS FD002"),
            ("cmapss_fd003", "CMAPSS FD003"),
            ("cmapss_fd004", "CMAPSS FD004"),
            ("smap_msl", "SMAP/MSL Telemetry"),
        ]
        options = "\n".join([f'<option value="{key}">{label}</option>' for key, label in sources])
        notice = (
            "Local only. No data leaves this machine. Files are stored under the selected workspace."
        )
        status = ""
        if error:
            status = f"<div class='error'>Error: {error}</div>"
        elif success:
            status = f"<div class='success'>{success}</div>"
        report_html = ""
        if report_link:
            report_html = f'<div class="link">Report link: <a href="{report_link}">{report_link}</a></div>'
        bundle_html = ""
        if bundle_link:
            bundle_html = f'<div class="link">Support bundle: <a href="{bundle_link}">Download ZIP</a></div>'

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Harmony Bridge Local UI</title>
  <style>
    :root {{
      --bg: #f6f2ec;
      --panel: #ffffff;
      --ink: #1f2a33;
      --muted: #5b6b76;
      --accent: #0e6f8a;
      --accent-2: #d9822b;
      --shadow: 0 12px 30px rgba(24, 39, 75, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Trebuchet MS", "Gill Sans", sans-serif;
      background: radial-gradient(circle at top left, #fdf8f0, var(--bg));
      color: var(--ink);
    }}
    header {{
      padding: 28px 36px 18px;
      background: linear-gradient(120deg, #f7efe2 0%, #f3f7f9 100%);
      border-bottom: 1px solid #e6e2d7;
    }}
    header h1 {{ margin: 0 0 6px; font-size: 26px; }}
    header p {{ margin: 0; color: var(--muted); font-size: 14px; }}
    main {{ padding: 24px 36px 40px; display: grid; gap: 18px; }}
    .banner {{
      background: #e7f6ee;
      color: #2f855a;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
    }}
    .card {{
      background: var(--panel);
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: var(--shadow);
      border: 1px solid #edf0f3;
    }}
    .label {{
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 1px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    button {{
      border: none;
      border-radius: 10px;
      padding: 8px 12px;
      font-weight: 600;
      cursor: pointer;
      background: var(--accent);
      color: #fff;
    }}
    input, select {{
      width: 100%;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid #d7dde2;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .error {{ color: #b91c1c; font-weight: 600; }}
    .success {{ color: #2f855a; font-weight: 600; }}
    .link a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); font-size: 13px; }}
  </style>
</head>
<body>
  <header>
    <h1>Harmony Bridge Local UI</h1>
    <p>Upload baseline + current files and generate drift reports locally.</p>
  </header>
  <main>
    <div class="banner">{notice}</div>
    {status}
    {report_html}
    {bundle_html}

    <div class="card">
      <div class="label">Workspace</div>
      <div class="muted">Default: {workspace}</div>
      <form method="post" enctype="multipart/form-data" action="/run">
        <input type="hidden" name="mode" value="baseline" />
        <div class="grid">
          <div>
            <label>Workspace path</label>
            <input name="workspace" type="text" value="{workspace}" />
          </div>
          <div>
            <label>Source type</label>
            <select name="source">{options}</select>
          </div>
          <div>
            <label>Baseline file</label>
            <input name="data_file" type="file" required />
          </div>
          <div>
            <label>Baseline run_meta.json (optional)</label>
            <input name="run_meta" type="file" />
          </div>
        </div>
        <div class="actions" style="margin-top: 10px;">
          <button type="submit">Install Baseline</button>
        </div>
      </form>
    </div>

    <div class="card">
      <div class="label">Analyze / Compare</div>
      <form method="post" enctype="multipart/form-data" action="/run">
        <input type="hidden" name="mode" value="current" />
        <div class="grid">
          <div>
            <label>Workspace path</label>
            <input name="workspace" type="text" value="{workspace}" />
          </div>
          <div>
            <label>Source type</label>
            <select name="source">{options}</select>
          </div>
          <div>
            <label>Current run file</label>
            <input name="data_file" type="file" required />
          </div>
          <div>
            <label>Current run_meta.json (optional)</label>
            <input name="run_meta" type="file" />
          </div>
        </div>
        <div class="actions" style="margin-top: 10px;">
          <button type="submit">Run Compare</button>
        </div>
      </form>
    </div>

    <div class="card">
      <div class="label">Feedback Hub</div>
      <div class="muted">Start the Local Feedback Service: <code>bin/hb feedback serve</code></div>
      <div class="muted">Open: <a href="http://127.0.0.1:8765/" target="_blank">http://127.0.0.1:8765/</a></div>
    </div>

    <div class="card">
      <div class="label">Watch Folder</div>
      <div class="muted">Local only. Polls for new files on a timer.</div>
      <div class="grid" style="margin-top: 8px;">
        <div>
          <label>Workspace path</label>
          <input id="watch-workspace" type="text" value="{workspace}" />
        </div>
        <div>
          <label>Watch directory</label>
          <input id="watch-dir" type="text" placeholder="/path/to/incoming" />
        </div>
        <div>
          <label>Source type</label>
          <select id="watch-source">{options}</select>
        </div>
        <div>
          <label>File pattern</label>
          <input id="watch-pattern" type="text" value="*" />
        </div>
        <div>
          <label>Interval</label>
          <select id="watch-interval">
            <option value="604800" selected>Weekly</option>
            <option value="2592000">Monthly</option>
            <option value="31536000">Yearly</option>
          </select>
        </div>
      </div>
      <div class="actions" style="margin-top: 10px;">
        <button type="button" onclick="startWatch()">Start Watch</button>
        <button type="button" onclick="stopWatch()" style="background: #d9822b;">Stop Watch</button>
      </div>
      <div class="muted" id="watch-status" style="margin-top: 6px;"></div>
    </div>
  </main>
  <script>
    function startWatch() {{
      const form = new FormData();
      form.append('workspace', document.getElementById('watch-workspace').value);
      form.append('watch_dir', document.getElementById('watch-dir').value);
      form.append('source', document.getElementById('watch-source').value);
      form.append('pattern', document.getElementById('watch-pattern').value);
      form.append('interval', document.getElementById('watch-interval').value);
      fetch('/watch/start', {{method: 'POST', body: form}}).then(r => r.json()).then(data => {{
        document.getElementById('watch-status').textContent = 'Watch started.';
      }}).catch(() => {{
        document.getElementById('watch-status').textContent = 'Unable to start watch.';
      }});
    }}
    function stopWatch() {{
      fetch('/watch/stop', {{method: 'POST'}}).then(r => r.json()).then(data => {{
        document.getElementById('watch-status').textContent = 'Watch stopped.';
      }}).catch(() => {{
        document.getElementById('watch-status').textContent = 'Unable to stop watch.';
      }});
    }}
  </script>
</body>
</html>
"""


def serve_local_ui(port=8890):
    server = HTTPServer(("127.0.0.1", int(port)), LocalUIHandler)
    server.watch_active = False
    server.watch_config = {}
    server.timeout = 1
    last_watch = 0
    print(f"local UI listening on http://127.0.0.1:{port}")
    while True:
        server.handle_request()
        if getattr(server, "watch_active", False):
            config = server.watch_config or {}
            interval = int(config.get("interval", 120))
            now = time.time()
            if now - last_watch >= interval:
                last_watch = now
                watch_dir = config.get("watch_dir")
                source = config.get("source", "pba_excel")
                pattern = config.get("pattern", "*")
                workspace = config.get("workspace")
                watch.run_watch(
                    watch_dir=watch_dir,
                    source=source,
                    pattern=pattern,
                    interval=interval,
                    workspace=workspace,
                    run_meta=None,
                    run_meta_dir=None,
                    open_report=True,
                    once=True,
                )
