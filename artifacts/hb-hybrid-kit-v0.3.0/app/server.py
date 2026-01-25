import csv
import json
import os
import time
import uuid
from collections import Counter
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


def _count_registry_metrics(registry_path):
    try:
        with open(registry_path, "r") as f:
            data = yaml.safe_load(f) or {}
        metrics = data.get("metrics") or []
        return len(metrics)
    except OSError:
        return None


def _load_report_json(summary_path):
    try:
        with open(summary_path, "r") as f:
            summary = json.load(f)
        report_path = summary.get("report_json_path")
        if not report_path:
            return None
        with open(report_path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _confidence_label(top_drivers):
    scores = {"low": 1, "medium": 2, "high": 3}
    values = [scores.get(item.get("confidence", "").lower()) for item in top_drivers or []]
    values = [value for value in values if value]
    if not values:
        return "n/a"
    avg = sum(values) / len(values)
    if avg >= 2.5:
        return "high"
    if avg >= 1.5:
        return "medium"
    return "low"


def _trend_label(scores):
    if len(scores) < 2:
        return "stable", "flat"
    window = min(3, max(1, len(scores) // 2))
    if len(scores) < window * 2:
        delta = scores[-1] - scores[0]
        if abs(delta) <= 0.05:
            return "stable", "flat"
        return ("degrading", "up") if delta > 0 else ("improving", "down")
    prev_avg = sum(scores[-2 * window : -window]) / window
    last_avg = sum(scores[-window:]) / window
    delta = last_avg - prev_avg
    if abs(delta) <= 0.05:
        return "stable", "flat"
    return ("degrading", "up") if delta > 0 else ("improving", "down")


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
        report_json = _load_report_json(result.summary_path)
        reports.append(
            {
                "status": result.status,
                "report_url": f"/api/run/{result.run_id}/report",
                "summary_url": f"/api/run/{result.run_id}/summary",
                "run_id": result.run_id,
                "summary_path": result.summary_path,
                "report_json": report_json,
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
        registry_path = os.environ.get("HB_METRIC_REGISTRY", "metric_registry.yaml")
        registry_total = _count_registry_metrics(registry_path) or 0
        driver_counts = Counter()
        drift_scores = []
        warning_total = 0
        fail_total = 0
        coverage_values = []
        confidence_values = []
        deep_drift_enabled = False
        run_rows = []
        rows = []
        for idx, item in enumerate(reports):
            status_class = "status-pill pass"
            if item["status"] == "PASS_WITH_DRIFT":
                status_class = "status-pill warn"
            elif item["status"] == "FAIL":
                status_class = "status-pill fail"
            report_json = item.get("report_json") or {}
            warnings = report_json.get("warnings") or []
            warning_total += len(warnings)
            fail_metrics = report_json.get("fail_metrics") or []
            fail_total += len(fail_metrics)
            drift_metrics = report_json.get("drift_metrics") or []
            top_drivers = (report_json.get("drift_attribution") or {}).get("top_drivers") or []
            decision_basis = report_json.get("decision_basis") or {}
            drift_score = decision_basis.get("drift_score")
            if drift_score is None and top_drivers:
                drift_score = top_drivers[0].get("drift_score") or top_drivers[0].get("score")
            if drift_score is not None:
                drift_scores.append(float(drift_score))
            missing_current = sum(1 for w in warnings if w.startswith("missing current metric"))
            if registry_total > 0:
                coverage_values.append(max(0.0, (registry_total - missing_current) / registry_total * 100.0))
            confidence_values.append(_confidence_label(top_drivers))
            distribution_drifts = report_json.get("distribution_drifts")
            if distribution_drifts is not None:
                deep_drift_enabled = True
            for entry in drift_metrics:
                metric_name = entry.get("metric")
                if metric_name:
                    driver_counts[metric_name] += 1
            for metric_name in fail_metrics:
                if metric_name:
                    driver_counts[metric_name] += 1
            drift_score_text = "n/a" if drift_score is None else f"{drift_score:.2f}"
            rows.append(
                f"<tr><td>{idx + 1}</td><td><span class=\"{status_class}\">{item['status']}</span></td>"
                f"<td><a class=\"link\" href=\"{item['report_url']}\">Open report</a></td>"
                f"<td><a class=\"link\" href=\"{item['summary_url']}\">Open summary</a></td></tr>"
            )
            run_rows.append(
                "<tr>"
                f"<td>{idx + 1}</td>"
                f"<td>{item.get('run_id', '')}</td>"
                f"<td><span class=\"{status_class}\">{item['status']}</span></td>"
                f"<td>{drift_score_text}</td>"
                f"<td>{len(warnings)}</td>"
                f"<td>{len(fail_metrics)}</td>"
                f"<td><a class=\"link\" href=\"{item['report_url']}\">report</a></td>"
                f"<td><a class=\"link\" href=\"{item['summary_url']}\">summary</a></td>"
                "</tr>"
            )
        table = "\n".join(rows)
        timeline = "\n".join(run_rows)
        current_status = reports[-1]["status"]
        trend_label, trend_arrow = _trend_label(drift_scores)
        avg_drift = None
        avg_change = "flat"
        if drift_scores:
            avg_drift = sum(drift_scores) / len(drift_scores)
            avg_change = trend_arrow
        avg_drift_text = "n/a"
        if avg_drift is not None:
            avg_drift_text = f"{avg_drift:.2f} ({avg_change})"
        coverage_text = "n/a"
        if coverage_values:
            coverage_text = f"{sum(coverage_values) / len(coverage_values):.1f}%"
        confidence_summary = "n/a"
        if confidence_values:
            counts = Counter(confidence_values)
            confidence_summary = counts.most_common(1)[0][0]
        top_recurring = driver_counts.most_common(5)
        top_recurring_html = (
            "<ul>" + "".join(f"<li>{name} ({count})</li>" for name, count in top_recurring) + "</ul>"
            if top_recurring
            else "<div class=\"muted\">none</div>"
        )
        deep_drift_text = "on" if deep_drift_enabled else "unknown"
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
      margin-bottom: 16px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .summary-card {{
      background: #fffdf9;
      border-radius: 14px;
      padding: 12px 14px;
      border: 1px solid rgba(30, 41, 59, 0.08);
    }}
    .summary-label {{
      font-size: 11px;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .summary-value {{
      font-size: 16px;
      font-weight: 700;
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
        <span class="status-pill {'pass' if current_status == 'PASS' else 'warn' if current_status == 'PASS_WITH_DRIFT' else 'fail'}">
          {current_status}
        </span>
        <span class="tag">Local-Only • No Uploads</span>
      </div>
      <div class="summary-grid">
        <div class="summary-card">
          <div class="summary-label">Trend ({len(reports)} runs)</div>
          <div class="summary-value">{trend_label}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Avg Drift Score</div>
          <div class="summary-value">{avg_drift_text}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Warnings / Fails</div>
          <div class="summary-value">{warning_total} / {fail_total}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Coverage</div>
          <div class="summary-value">{coverage_text}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Sample Sufficiency</div>
          <div class="summary-value">{confidence_summary}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Deep Drift</div>
          <div class="summary-value">{deep_drift_text}</div>
        </div>
      </div>
      <div class="summary-card" style="margin-bottom: 16px;">
        <div class="summary-label">Top Recurring Drivers</div>
        {top_recurring_html}
      </div>
      <table>
        <thead><tr><th>#</th><th>Status</th><th>Report</th><th>Summary</th></tr></thead>
        <tbody>{table}</tbody>
      </table>
      <div style="margin-top: 18px;">
        <div class="summary-label">Run Timeline</div>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Run ID</th>
              <th>Status</th>
              <th>Drift Score</th>
              <th>Warnings</th>
              <th>Fails</th>
              <th>Report</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>{timeline}</tbody>
        </table>
      </div>
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
