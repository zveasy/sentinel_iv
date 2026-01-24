import csv
import json
import os
import time
import uuid
from typing import List

import yaml

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from hb_core.compare import run_compare
from hb.adapters import nasa_http_tsv

app = FastAPI()
RUN_INDEX = {}
BASELINE_CACHE = {"signature": None, "schema_path": None, "profile_path": None}


def _ensure_dirs(path):
    os.makedirs(path, exist_ok=True)


def _save_upload(upload, dest_dir, prefix):
    _ensure_dirs(dest_dir)
    name = upload.filename or "upload"
    safe_name = name.replace("/", "_")
    out_path = os.path.join(dest_dir, f"{prefix}_{uuid.uuid4().hex}_{safe_name}")
    with open(out_path, "wb") as f:
        f.write(upload.file.read())
    return out_path


def _file_signature(path):
    try:
        return f"{os.path.getsize(path)}:{os.path.getmtime(path)}"
    except OSError:
        return None


def _detect_delimiter(sample_bytes):
    sample = sample_bytes.splitlines()[0] if sample_bytes else b""
    tab_count = sample.count(b"\t")
    comma_count = sample.count(b",")
    if tab_count > comma_count:
        return "\t"
    if comma_count > 0:
        return ","
    return "whitespace"


def _infer_column_types(rows, headers):
    types = {name: "str" for name in headers}
    for name in headers:
        values = []
        for row in rows:
            if name in row and row[name] not in ("", None):
                values.append(str(row[name]).strip())
        if not values:
            continue
        numeric = 0
        parsed = []
        for value in values:
            try:
                parsed.append(float(value))
                numeric += 1
            except ValueError:
                continue
        ratio = numeric / len(values) if values else 0.0
        if ratio >= 0.2 and parsed:
            if all(float(v).is_integer() for v in parsed):
                types[name] = "int"
            else:
                types[name] = "float"
        else:
            types[name] = "str"
    return types


def _build_schema_from_baseline(baseline_path, uploads_dir):
    with open(baseline_path, "rb") as f:
        sample_bytes = f.read(1024 * 64)
    delimiter = _detect_delimiter(sample_bytes)
    headers = []
    rows = []
    if delimiter == "whitespace":
        lines = sample_bytes.decode("utf-8", errors="replace").splitlines()
        if not lines:
            raise ValueError("No header row detected in baseline file.")
        headers = lines[0].split()
        for line in lines[1:101]:
            values = line.split()
            rows.append(dict(zip(headers, values)))
    else:
        text = sample_bytes.decode("utf-8", errors="replace")
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        headers = reader.fieldnames or []
        for idx, row in enumerate(reader):
            rows.append(row)
            if idx >= 100:
                break
    if not headers:
        raise ValueError("No header row detected in baseline file.")
    inferred_types = _infer_column_types(rows, headers)
    numeric_cols = [name for name, col_type in inferred_types.items() if col_type in ("int", "float")]
    if not numeric_cols:
        raise ValueError("No numeric columns detected in baseline file.")
    schema = {
        "name": f"baseline_{uuid.uuid4().hex[:6]}",
        "format": "tabular",
        "delimiter": delimiter,
        "header": True,
        "required_columns": [],
        "optional_columns": headers,
        "column_types": inferred_types,
        "allow_extra_columns": True,
    }
    schema_dir = os.path.join(uploads_dir, "schemas")
    os.makedirs(schema_dir, exist_ok=True)
    schema_path = os.path.join(schema_dir, "schema.yaml")
    with open(schema_path, "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False)
    return schema_path


def _build_baseline_profile(baseline_path, uploads_dir):
    ext = os.path.splitext(baseline_path)[1].lower()
    if ext != ".tsv":
        return None
    profile_path = os.path.join(uploads_dir, "baseline_profile.json")
    os.environ["HB_BASELINE_PROFILE_OUT"] = profile_path
    os.environ["HB_STREAM_INGEST"] = "1"
    try:
        nasa_http_tsv.parse_stream(baseline_path)
    finally:
        if "HB_BASELINE_PROFILE_OUT" in os.environ:
            del os.environ["HB_BASELINE_PROFILE_OUT"]
        if "HB_STREAM_INGEST" in os.environ:
            del os.environ["HB_STREAM_INGEST"]
    return profile_path if os.path.exists(profile_path) else None


@app.post("/api/profile")
def build_profile(baseline_file: UploadFile = File(...)):
    uploads_dir = os.path.join(os.getcwd(), "output", "profiles")
    baseline_path = _save_upload(baseline_file, uploads_dir, "baseline")
    signature = _file_signature(baseline_path)
    try:
        schema_path = _build_schema_from_baseline(baseline_path, uploads_dir)
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    profile_path = _build_baseline_profile(baseline_path, uploads_dir)
    BASELINE_CACHE.update(
        {"signature": signature, "schema_path": schema_path, "profile_path": profile_path}
    )
    if not profile_path:
        return JSONResponse(
            {"status": "ok", "schema_path": schema_path, "profile_path": None},
            status_code=200,
        )
    return JSONResponse(
        {"status": "ok", "schema_path": schema_path, "profile_path": profile_path},
        status_code=200,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/compare")
def compare(
    baseline_file: UploadFile = File(...),
    run_files: List[UploadFile] = File(...),
    schema_file: UploadFile = File(None),
    schema_mode: str = Form("auto"),
    out_dir: str = Form(""),
):
    if schema_mode not in {"auto", "file", "none"}:
        return JSONResponse({"error": "invalid schema_mode"}, status_code=400)
    if schema_mode == "file" and not schema_file:
        return JSONResponse({"error": "schema_file required for schema_mode=file"}, status_code=400)

    if not out_dir:
        out_dir = os.path.join(os.getcwd(), "output", time.strftime("%Y%m%d_%H%M%S"))
    _ensure_dirs(out_dir)
    uploads_dir = os.path.join(out_dir, "uploads")
    baseline_path = _save_upload(baseline_file, uploads_dir, "baseline")
    schema_path = None
    if schema_file:
        schema_path = _save_upload(schema_file, uploads_dir, "schema")

    signature = _file_signature(baseline_path)
    if BASELINE_CACHE["signature"] == signature and BASELINE_CACHE["schema_path"]:
        cached_schema_path = BASELINE_CACHE["schema_path"]
    else:
        cached_schema_path = _build_schema_from_baseline(baseline_path, uploads_dir)
        BASELINE_CACHE.update(
            {"signature": signature, "schema_path": cached_schema_path, "profile_path": None}
        )

    baseline_profile_path = None
    if BASELINE_CACHE["signature"] == signature and BASELINE_CACHE["profile_path"]:
        baseline_profile_path = BASELINE_CACHE["profile_path"]
    else:
        baseline_profile_path = _build_baseline_profile(baseline_path, uploads_dir)
        BASELINE_CACHE["profile_path"] = baseline_profile_path

    if schema_mode == "auto" and cached_schema_path:
        schema_mode = "file"
        schema_path = cached_schema_path
    reports = []
    for run_file in run_files:
        run_path = _save_upload(run_file, uploads_dir, "run")
        result = run_compare(
            baseline_path=baseline_path,
            run_path=run_path,
            out_dir=out_dir,
            schema_mode=None if schema_mode == "none" else schema_mode,
            schema_path=schema_path,
            thresholds_path=os.environ.get("HB_BASELINE_POLICY", "baseline_policy.yaml"),
            run_meta=None,
            baseline_profile_path=baseline_profile_path,
        )
        RUN_INDEX[result.run_id] = {
            "report_path": result.report_path,
            "summary_path": result.summary_path,
        }
        reports.append(
            {
                "status": result.status,
                "report_url": f"/api/run/{result.run_id}/report",
                "summary_url": f"/api/run/{result.run_id}/summary",
                "run_id": result.run_id,
            }
        )
    overall_status = "PASS"
    for item in reports:
        if item["status"] == "FAIL":
            overall_status = "FAIL"
            break
        if item["status"] == "PASS_WITH_DRIFT":
            overall_status = "PASS_WITH_DRIFT"
    combined_url = None
    if len(reports) > 1:
        combined_path = os.path.join(out_dir, "combined_report.html")
        rows = []
        for idx, item in enumerate(reports):
            status_class = "status-pill pass"
            if item["status"] == "PASS_WITH_DRIFT":
                status_class = "status-pill warn"
            elif item["status"] == "FAIL":
                status_class = "status-pill fail"
            rows.append(
                f"<tr><td>{idx + 1}</td><td><span class=\"{status_class}\">{item['status']}</span></td>"
                f"<td><a class=\"link\" href=\"{item['report_url']}\">Open report</a></td>"
                f"<td><a class=\"link\" href=\"{item['summary_url']}\">Open summary</a></td></tr>"
            )
        table = "\n".join(rows)
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Combined Reports</title>
  <style>
    :root {{
      --bg: #f6f0e8;
      --panel: #ffffff;
      --ink: #1b1b1f;
      --muted: #5e6a72;
      --accent: #e86f3b;
      --accent-2: #0f766e;
      --ok: #2f855a;
      --warn: #b45309;
      --fail: #b91c1c;
      --shadow: 0 18px 40px rgba(16, 24, 40, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Manrope", "Trebuchet MS", "Gill Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 20%, rgba(255, 215, 160, 0.5), transparent 40%),
        radial-gradient(circle at 85% 15%, rgba(15, 118, 110, 0.2), transparent 45%),
        linear-gradient(180deg, #fbf6ef 0%, #f4ede3 100%);
    }}
    header {{
      padding: 28px 36px 16px;
      border-bottom: 1px solid rgba(232, 111, 59, 0.15);
      background: linear-gradient(120deg, rgba(255, 238, 219, 0.85) 0%, rgba(236, 246, 245, 0.9) 100%);
    }}
    header h1 {{
      margin: 0 0 6px;
      font-family: "Space Grotesk", "Manrope", sans-serif;
      font-size: 26px;
      letter-spacing: 0.2px;
    }}
    header p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    main {{
      padding: 22px 36px 40px;
      max-width: 1100px;
      margin: 0 auto;
    }}
    .card {{
      background: var(--panel);
      border-radius: 18px;
      padding: 18px 20px;
      box-shadow: var(--shadow);
      border: 1px solid rgba(30, 41, 59, 0.08);
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.6px;
    }}
    .pass {{ background: rgba(47, 133, 90, 0.15); color: var(--ok); }}
    .warn {{ background: rgba(180, 83, 9, 0.15); color: var(--warn); }}
    .fail {{ background: rgba(185, 28, 28, 0.15); color: var(--fail); }}
    table {{
      border-collapse: collapse;
      width: 100%;
      background: #fffdf9;
      border-radius: 12px;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid #ece4d8;
      padding: 10px 12px;
      text-align: left;
      font-size: 14px;
    }}
    th {{
      background: #f8f2e9;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .link {{
      color: var(--accent);
      font-weight: 600;
      text-decoration: none;
    }}
    .link:hover {{ text-decoration: underline; }}
    .summary {{
      display: flex;
      gap: 12px;
      align-items: center;
      margin-bottom: 14px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.12);
      color: var(--accent-2);
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.4px;
    }}
    @media (max-width: 640px) {{
      header, main {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Combined Reports</h1>
    <p>Multi-run summary for this compare.</p>
  </header>
  <main>
    <div class="card">
      <div class="summary">
        <span class="status-pill {'pass' if overall_status == 'PASS' else 'warn' if overall_status == 'PASS_WITH_DRIFT' else 'fail'}">
          {overall_status}
        </span>
        <span class="tag">Local-Only • No Uploads</span>
      </div>
      <table>
        <thead><tr><th>#</th><th>Status</th><th>Report</th><th>Summary</th></tr></thead>
        <tbody>{table}</tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""
        with open(combined_path, "w") as f:
            f.write(html)
        combined_url = "/api/combined-report"
        RUN_INDEX["combined"] = {"path": combined_path}
    payload = {"status": overall_status, "reports": reports, "combined_report_url": combined_url}
    return JSONResponse(payload)


@app.get("/api/run/{run_id}/report")
def get_report(run_id: str):
    entry = RUN_INDEX.get(run_id)
    if not entry:
        return JSONResponse({"error": "report not found"}, status_code=404)
    path = entry.get("report_path")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "report missing"}, status_code=404)
    with open(path, "rb") as f:
        return Response(content=f.read(), media_type="text/html")


@app.get("/api/run/{run_id}/summary")
def get_summary(run_id: str):
    entry = RUN_INDEX.get(run_id)
    if not entry:
        return JSONResponse({"error": "summary not found"}, status_code=404)
    path = entry.get("summary_path")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "summary missing"}, status_code=404)
    with open(path, "rb") as f:
        return Response(content=f.read(), media_type="application/json")


@app.get("/api/combined-report")
def get_combined_report():
    entry = RUN_INDEX.get("combined")
    if not entry:
        return JSONResponse({"error": "combined report not found"}, status_code=404)
    path = entry.get("path")
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "combined report missing"}, status_code=404)
    with open(path, "rb") as f:
        return Response(content=f.read(), media_type="text/html")


@app.get("/", response_class=HTMLResponse)
def index():
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Harmony Bridge Local Compare</title>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f6f0e8;
      --panel: #ffffff;
      --ink: #1b1b1f;
      --muted: #5e6a72;
      --accent: #e86f3b;
      --accent-2: #0f766e;
      --ok: #2f855a;
      --warn: #b45309;
      --fail: #b91c1c;
      --shadow: 0 18px 40px rgba(16, 24, 40, 0.12);
      --ring: 0 0 0 3px rgba(232, 111, 59, 0.25);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Manrope", "Trebuchet MS", "Gill Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 20%, rgba(255, 215, 160, 0.5), transparent 40%),
        radial-gradient(circle at 85% 15%, rgba(15, 118, 110, 0.2), transparent 45%),
        linear-gradient(180deg, #fbf6ef 0%, #f4ede3 100%);
    }
    header {
      padding: 34px 40px 18px;
      border-bottom: 1px solid rgba(232, 111, 59, 0.15);
      background: linear-gradient(120deg, rgba(255, 238, 219, 0.85) 0%, rgba(236, 246, 245, 0.9) 100%);
    }
    header h1 {
      margin: 0 0 6px;
      font-family: "Space Grotesk", "Manrope", sans-serif;
      font-size: 28px;
      letter-spacing: 0.2px;
    }
    header p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }
    main {
      padding: 28px 40px 40px;
      display: grid;
      gap: 20px;
      max-width: 1100px;
      margin: 0 auto;
    }
    .card {
      background: var(--panel);
      border-radius: 18px;
      padding: 22px 24px;
      box-shadow: var(--shadow);
      border: 1px solid rgba(30, 41, 59, 0.08);
    }
    label {
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    input, select, button {
      font-size: 14px;
    }
    input[type="text"], select {
      width: 100%;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid #d8dee4;
      background: #fffdf9;
    }
    input[type="file"] {
      width: 100%;
    }
    input[type="text"]:focus, select:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: var(--ring);
      background: #ffffff;
    }
    button {
      border: none;
      background: linear-gradient(135deg, var(--accent) 0%, #f18b5b 100%);
      color: #fff;
      padding: 11px 18px;
      border-radius: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12); }
    .row {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .hero {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
    }
    .hero .tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.12);
      color: var(--accent-2);
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.4px;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.6px;
    }
    .pass { background: rgba(47, 133, 90, 0.15); color: var(--ok); }
    .warn { background: rgba(180, 83, 9, 0.15); color: var(--warn); }
    .fail { background: rgba(185, 28, 28, 0.15); color: var(--fail); }
    .muted { color: var(--muted); font-size: 13px; }
    .note {
      font-size: 13px;
      color: var(--muted);
      line-height: 1.5;
      margin-top: 6px;
    }
    @media (max-width: 640px) {
      header, main { padding: 20px; }
      .hero { flex-direction: column; align-items: flex-start; }
    }
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <div>
        <h1>Harmony Bridge Local Compare</h1>
        <p>Runs locally on your machine. No data ever leaves this computer.</p>
      </div>
      <div class="tag">Local-Only • No Uploads</div>
    </div>
  </header>
  <main>
    <form id="compare-form" class="card">
      <div class="row">
        <div>
          <label>Baseline File</label>
          <input type="file" name="baseline_file" required />
        </div>
        <div>
          <label>Run File</label>
          <input type="file" name="run_files" multiple required />
        </div>
      </div>
      <div class="row" style="margin-top: 16px;">
        <div>
          <label>Schema Mode</label>
          <select name="schema_mode" id="schema_mode">
            <option value="auto" selected>Auto</option>
            <option value="file">Upload Schema</option>
            <option value="none">None</option>
          </select>
          <div class="note">Auto builds a schema from the baseline file.</div>
        </div>
        <div>
          <label>Schema File (optional)</label>
          <input type="file" name="schema_file" id="schema_file" />
          <div class="note">Use when you already have a schema.</div>
        </div>
        <div>
          <label>Output Directory</label>
          <input type="text" name="out_dir" placeholder="./output/20250101_120000" />
          <div class="note">Default is timestamped in ./output/</div>
        </div>
      </div>
      <div style="margin-top: 18px;">
        <button type="submit">Run Compare</button>
        <span class="muted" style="margin-left: 12px;" id="status-text">Waiting for files...</span>
      </div>
    </form>

    <div class="card" id="result-card" style="display:none;">
      <div class="row">
        <div>
          <label>Result</label>
          <div id="status-pill" class="status-pill pass">PASS</div>
        </div>
        <div>
          <label>Report</label>
          <div><a id="report-link" href="#" target="_blank">Open report</a></div>
        </div>
        <div>
          <label>Summary</label>
          <div><a id="summary-link" href="#" target="_blank">Open summary</a></div>
        </div>
      </div>
      <div style="margin-top: 12px;">
        <label>All Runs</label>
        <ul id="report-list" class="muted" style="margin: 6px 0 0; padding-left: 18px;"></ul>
      </div>
    </div>
  </main>
  <script>
    const form = document.getElementById('compare-form');
    const statusText = document.getElementById('status-text');
    const baselineInput = document.querySelector('input[name="baseline_file"]');
    const resultCard = document.getElementById('result-card');
    const statusPill = document.getElementById('status-pill');
    const reportLink = document.getElementById('report-link');
    const summaryLink = document.getElementById('summary-link');
    const reportList = document.getElementById('report-list');

    baselineInput.addEventListener('change', async () => {
      if (!baselineInput.files || baselineInput.files.length === 0) return;
      statusText.textContent = 'Building baseline profile...';
      const formData = new FormData();
      formData.append('baseline_file', baselineInput.files[0]);
      const response = await fetch('/api/profile', { method: 'POST', body: formData });
      if (!response.ok) {
        const payload = await response.json();
        statusText.textContent = payload.error || 'Profile build failed.';
        return;
      }
      statusText.textContent = 'Baseline profile ready.';
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      statusText.textContent = 'Running compare...';
      const formData = new FormData(form);
      const response = await fetch('/api/compare', { method: 'POST', body: formData });
      const payload = await response.json();
      if (!response.ok) {
        statusText.textContent = payload.error || 'Compare failed.';
        return;
      }
      const status = payload.status || 'UNKNOWN';
      statusPill.textContent = status;
      statusPill.className = 'status-pill ' + (
        status === 'PASS' ? 'pass' : status === 'PASS_WITH_DRIFT' ? 'warn' : 'fail'
      );
      const reports = payload.reports || [];
      const combinedReportUrl = payload.combined_report_url || null;
      if (combinedReportUrl) {
        reportLink.href = combinedReportUrl;
        reportLink.textContent = 'Open combined report';
      } else if (reports.length > 0) {
        reportLink.href = reports[0].report_url;
        reportLink.textContent = 'Open report';
      }
      if (reports.length > 0) {
        summaryLink.href = reports[0].summary_url;
      }
      reportList.innerHTML = '';
      reports.forEach((item, idx) => {
        const li = document.createElement('li');
        li.innerHTML = `Run ${idx + 1} — ${item.status} — <a href="${item.report_url}" target="_blank">report</a> | <a href="${item.summary_url}" target="_blank">summary</a>`;
        reportList.appendChild(li);
      });
      resultCard.style.display = 'block';
      statusText.textContent = 'Done.';
    });
  </script>
</body>
</html>
"""
    return HTMLResponse(html)


def run(host="127.0.0.1", port=8765):
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
