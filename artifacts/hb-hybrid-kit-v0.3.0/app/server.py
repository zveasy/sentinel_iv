import json
import os
import time
import uuid

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from hb_core.compare import run_compare

app = FastAPI()
RUN_INDEX = {}


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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/compare")
def compare(
    baseline_file: UploadFile = File(...),
    run_file: UploadFile = File(...),
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
    run_path = _save_upload(run_file, uploads_dir, "run")
    schema_path = None
    if schema_file:
        schema_path = _save_upload(schema_file, uploads_dir, "schema")

    result = run_compare(
        baseline_path=baseline_path,
        run_path=run_path,
        out_dir=out_dir,
        schema_mode=None if schema_mode == "none" else schema_mode,
        schema_path=schema_path,
        thresholds_path=os.environ.get("HB_BASELINE_POLICY", "baseline_policy.yaml"),
        run_meta=None,
    )
    RUN_INDEX[result.run_id] = {
        "report_path": result.report_path,
        "summary_path": result.summary_path,
    }
    payload = {
        "status": result.status,
        "report_url": f"/api/run/{result.run_id}/report",
        "summary_url": f"/api/run/{result.run_id}/summary",
        "run_id": result.run_id,
    }
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
          <input type="file" name="run_file" required />
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
    </div>
  </main>
  <script>
    const form = document.getElementById('compare-form');
    const statusText = document.getElementById('status-text');
    const resultCard = document.getElementById('result-card');
    const statusPill = document.getElementById('status-pill');
    const reportLink = document.getElementById('report-link');
    const summaryLink = document.getElementById('summary-link');

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
      reportLink.href = payload.report_url;
      summaryLink.href = payload.summary_url;
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
