import json
import os
import shutil
import subprocess

from hb.io import write_json


def _narrative(item):
    parts = []
    unit = item.get("unit") or ""
    delta = item.get("delta")
    if delta is not None:
        parts.append(f"delta {delta}{unit}".strip())
    if item.get("drift_threshold") is not None:
        parts.append(f"threshold {item['drift_threshold']}{unit}".strip())
    if item.get("percent_change") is not None and item.get("drift_percent") is not None:
        parts.append(
            f"percent {round(item['percent_change'], 2)}% > {item['drift_percent']}%"
        )
    if item.get("min_effect") is not None:
        parts.append(f"min_effect {item['min_effect']}{unit}".strip())
    return "; ".join(parts)


def write_report(report_dir, payload):
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, "drift_report.json")
    html_path = os.path.join(report_dir, "drift_report.html")
    write_json(json_path, payload)

    drift_rows = []
    diff_rows = []
    def _cell(value, suffix=""):
        if value is None:
            return "<span class=\"muted\">n/a</span>"
        return f"{value}{suffix}"

    drift_items = payload.get("top_drifts", payload.get("drift_metrics", []))
    max_abs_delta = 0
    for item in drift_items:
        delta = item.get("delta")
        if isinstance(delta, (int, float)):
            max_abs_delta = max(max_abs_delta, abs(delta))
    for item in drift_items:
        threshold_cell = _cell(item.get("drift_threshold"))
        percent_threshold_cell = _cell(item.get("drift_percent"))
        if item.get("drift_threshold") is not None and abs(item.get("delta", 0)) > item.get("drift_threshold"):
            threshold_cell = f"<strong class=\"highlight\">{item['drift_threshold']}</strong>"
        if (
            item.get("drift_percent") is not None
            and item.get("percent_change") is not None
            and abs(item.get("percent_change", 0)) > item.get("drift_percent")
        ):
            percent_threshold_cell = f"<strong class=\"highlight\">{item['drift_percent']}</strong>"
        drift_rows.append(
            "<tr>"
            f"<td>{item['metric']}</td>"
            f"<td>{_cell(item.get('baseline'))}</td>"
            f"<td>{_cell(item.get('current'))}</td>"
            f"<td>{_cell(item.get('delta'))}</td>"
            f"<td>{_cell(item.get('percent_change'))}</td>"
            f"<td>{threshold_cell}</td>"
            f"<td>{percent_threshold_cell}</td>"
            f"<td>{item.get('unit') or ''}</td>"
            f"<td>{item.get('severity') or ''}</td>"
            f"<td>{_narrative(item)}</td>"
            "</tr>"
        )
        delta = item.get("delta")
        if delta is None or max_abs_delta == 0:
            bar_width = 0
        else:
            bar_width = min(100, round(abs(delta) / max_abs_delta * 100))
        bar_class = "bar-pos" if (delta or 0) >= 0 else "bar-neg"
        diff_rows.append(
            "<tr>"
            f"<td>{item['metric']}</td>"
            f"<td>{_cell(item.get('baseline'))}</td>"
            f"<td>{_cell(item.get('current'))}</td>"
            f"<td>{_cell(delta)}</td>"
            f"<td><div class=\"bar-track\"><div class=\"bar {bar_class}\" style=\"width:{bar_width}%\"></div></div></td>"
            "</tr>"
        )
    drift_table = "\n".join(drift_rows)
    diff_table = "\n".join(diff_rows) if diff_rows else "<tr><td colspan=\"5\">none</td></tr>"

    baseline_reason = payload.get("baseline_reason") or "unknown"
    match_level = payload.get("baseline_match_level") or "none"
    match_score = payload.get("baseline_match_score")
    match_possible = payload.get("baseline_match_possible")
    match_line = f"{match_level}"
    if match_score is not None and match_possible is not None:
        match_line = f"{match_level} ({match_score}/{match_possible})"
    match_fields = ", ".join(payload.get("baseline_match_fields") or [])

    drivers = []
    for item in (payload.get("drift_attribution") or {}).get("top_drivers", [])[:3]:
        effect = item.get("effect_size") or {}
        if effect.get("percent") is not None:
            effect_text = f"{round(effect['percent'], 2)}%"
        elif effect.get("zscore") is not None:
            effect_text = f"z={round(effect['zscore'], 2)}"
        elif effect.get("delta") is not None:
            effect_text = f"delta={round(effect['delta'], 4)}"
        else:
            effect_text = "n/a"
        drivers.append(f"{item.get('metric_name')} {item.get('direction')} ({effect_text})")
    top_drivers = ", ".join(drivers) if drivers else "none"

    dist_rows = []
    for item in payload.get("distribution_drifts", []):
        dist_rows.append(
            "<tr>"
            f"<td>{item['metric']}</td>"
            f"<td>{item.get('method')}</td>"
            f"<td>{item.get('statistic')}</td>"
            f"<td>{item.get('threshold')}</td>"
            f"<td>{item.get('sample_count_baseline')}</td>"
            f"<td>{item.get('sample_count_current')}</td>"
            "</tr>"
        )
    dist_table = "\n".join(dist_rows) if dist_rows else ""
    dist_section = ""
    if dist_rows:
        dist_section = (
            "<table>"
            "<thead>"
            "<tr>"
            "<th>Metric</th>"
            "<th>Method</th>"
            "<th>Statistic</th>"
            "<th>Threshold</th>"
            "<th>Baseline Samples</th>"
            "<th>Current Samples</th>"
            "</tr>"
            "</thead>"
            f"<tbody>{dist_table}</tbody>"
            "</table>"
        )
    else:
        dist_section = "<div class=\"muted\">No distribution drift detected.</div>"

    attribution_rows = []
    top_attribution = (payload.get("drift_attribution") or {}).get("top_drivers", [])[:5]
    for item in top_attribution:
        effect = item.get("effect_size") or {}
        parts = []
        if effect.get("percent") is not None:
            parts.append(f"{round(effect['percent'], 2)}%")
        if effect.get("zscore") is not None:
            parts.append(f"z={round(effect['zscore'], 2)}")
        if effect.get("ks") is not None:
            parts.append(f"ks={round(effect['ks'], 3)}")
        if not parts and effect.get("delta") is not None:
            parts.append(f"delta={round(effect['delta'], 4)}")
        effect_text = ", ".join(parts) if parts else "n/a"

        baseline_stats = item.get("baseline_stats") or {}
        current_stats = item.get("current_stats") or {}
        baseline_text = (
            f"mean={baseline_stats.get('mean')} med={baseline_stats.get('median')} p95={baseline_stats.get('p95')}"
        )
        current_text = (
            f"mean={current_stats.get('mean')} med={current_stats.get('median')} p95={current_stats.get('p95')}"
        )

        onset = item.get("onset") or {}
        onset_text = "Onset: gradual increase across analysis window"
        if onset.get("sustained_index") is not None:
            onset_text = f"Onset (approx): idx ~{onset.get('sustained_index')} (p={onset.get('persistence')})"
        elif onset.get("first_exceed_index") is not None:
            onset_text = f"Onset (approx): idx ~{onset.get('first_exceed_index')} (p={onset.get('persistence')})"

        sources = item.get("raw_features") or []
        corr_items = item.get("raw_feature_correlations") or []
        corr_text = ""
        if corr_items:
            corr_text = "; ".join(
                f"{entry['feature']} corr={round(entry['corr'], 3) if entry['corr'] is not None else 'n/a'}"
                for entry in corr_items
            )
        sources_text = ", ".join(sources) if sources else "aggregate(metric-only)"
        if corr_text:
            sources_text = f"{sources_text} ({corr_text})"
        elif item.get("correlation_note"):
            sources_text = f"{sources_text} ({item.get('correlation_note')})"

        evidence = item.get("evidence") or []
        evidence_rows = []
        for row in evidence:
            evidence_rows.append(
                "<tr>"
                f"<td>{row.get('index')}</td>"
                f"<td>{row.get('value')}</td>"
                f"<td>{row.get('drift_score')}</td>"
                "</tr>"
            )
        evidence_table = (
            "<table><thead><tr><th>Idx</th><th>Value</th><th>Score</th></tr></thead>"
            f"<tbody>{''.join(evidence_rows)}</tbody></table>"
            if evidence_rows
            else "n/a"
        )
        if not evidence_rows:
            baseline_median = baseline_stats.get("median")
            current_median = current_stats.get("median")
            if baseline_median is not None and current_median is not None:
                evidence_table = f"baseline median={baseline_median} -> current median={current_median}"

        decision_basis = ", ".join(item.get("decision_basis") or []) or "n/a"
        attribution_rows.append(
            "<tr>"
            f"<td>{item.get('metric_name')}</td>"
            f"<td>{item.get('direction')}</td>"
            f"<td>{effect_text}</td>"
            f"<td>{baseline_text}</td>"
            f"<td>{current_text}</td>"
            f"<td>{onset_text}</td>"
            f"<td>{sources_text}</td>"
            f"<td>{decision_basis}</td>"
            f"<td>{evidence_table}</td>"
            "</tr>"
        )
    attribution_table = (
        "\n".join(attribution_rows)
        if attribution_rows
        else "<tr><td colspan=\"9\">none</td></tr>"
    )

    baseline_warning = payload.get("baseline_warning")
    mismatch_expected = "yes" if payload.get("context_mismatch_expected") else "no"
    top_driver_list = (payload.get("drift_attribution") or {}).get("top_drivers") or []
    top_driver = top_driver_list[0] if top_driver_list else {}

    decision_basis = payload.get("decision_basis") or {}
    decision_basis_line = "n/a"
    if decision_basis:
        decision_basis_line = (
            f"score={decision_basis.get('drift_score')} "
            f"warn={decision_basis.get('warn_threshold')} "
            f"fail={decision_basis.get('fail_threshold')} "
            f"persistence={decision_basis.get('persistence_cycles')} "
            f"type={decision_basis.get('score_type')}"
        )
    decision_basis_human = "Decision basis: n/a"
    if top_driver:
        effect = top_driver.get("effect_size") or {}
        percent = effect.get("percent")
        delta = effect.get("delta")
        warn_percent = top_driver.get("drift_percent")
        warn_abs = top_driver.get("drift_threshold") or decision_basis.get("warn_threshold")
        persistence = decision_basis.get("persistence_cycles")
        parts = []
        if percent is not None:
            parts.append(f"{round(percent, 2)}% increase")
        elif delta is not None:
            parts.append(f"{round(delta, 4)} increase")
        if warn_percent is not None:
            parts.append(f"exceeded warn threshold ({warn_percent}%)")
        elif warn_abs is not None:
            parts.append(f"exceeded warn threshold ({warn_abs})")
        if persistence is not None:
            parts.append(f"for {persistence} consecutive cycles")
        if parts:
            decision_basis_human = "Decision basis: " + " ".join(parts)
    why_line = None
    if payload.get("status") and (payload.get("drift_attribution") or {}).get("top_drivers"):
        driver = (payload.get("drift_attribution") or {}).get("top_drivers", [])[0]
        effect = driver.get("effect_size") or {}
        basis = decision_basis or {}
        delta = effect.get("delta")
        percent = effect.get("percent")
        warn = basis.get("warn_threshold")
        persistence = basis.get("persistence_cycles")
        parts = []
        metric_name = driver.get("metric_name")
        if metric_name:
            parts.append(metric_name.replace("_", " "))
        if percent is not None:
            parts.append(f"increased by {round(percent, 2)}%")
        if delta is not None:
            parts.append(f"({round(delta, 4)})")
        if warn is not None:
            parts.append(f"exceeding warn threshold {warn}")
        if persistence is not None:
            parts.append(f"for {persistence} consecutive cycles")
        if parts:
            why_line = "Why: " + " ".join(parts) + "."

    feedback_payload = {
        "hb_version": payload.get("hb_version"),
        "source_type": payload.get("source_type"),
        "metric": top_driver.get("metric_name"),
        "decision": payload.get("status"),
        "top_driver": top_driver.get("metric_name"),
        "effect_size": (
            top_driver.get("effect_size", {}).get("percent")
        ),
        "thresholds": {
            "warn": decision_basis.get("warn_threshold"),
            "percent": top_driver.get("drift_percent"),
            "persistence": decision_basis.get("persistence_cycles"),
        },
    }
    feedback_payload_json = json.dumps(feedback_payload)

    status_value = payload.get("status", "UNKNOWN")
    status_class = "status-unknown"
    if status_value == "PASS":
        status_class = "status-pass"
    elif status_value == "PASS_WITH_DRIFT":
        status_class = "status-drift"
    elif status_value == "FAIL":
        status_class = "status-fail"
    no_metrics_hint = ""
    if status_value == "NO_METRICS":
        no_metrics_hint = "No metrics were evaluated. Check schema/registry mapping."

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Harmony Bridge Drift Report</title>
  <style>
    :root {{
      --bg: #f6f2ec;
      --panel: #ffffff;
      --ink: #1f2a33;
      --muted: #5b6b76;
      --accent: #0e6f8a;
      --accent-2: #d9822b;
      --ok: #2f855a;
      --fail: #b91c1c;
      --shadow: 0 12px 30px rgba(24, 39, 75, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Avenir Next", "Trebuchet MS", "Gill Sans", sans-serif;
      margin: 0;
      color: var(--ink);
      background: radial-gradient(circle at top left, #fdf8f0, var(--bg));
    }}
    header {{
      padding: 28px 36px 18px;
      background: linear-gradient(120deg, #f7efe2 0%, #f3f7f9 100%);
      border-bottom: 1px solid #e6e2d7;
    }}
    header h1 {{
      margin: 0 0 6px;
      font-size: 26px;
      letter-spacing: 0.2px;
    }}
    header p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    main {{
      padding: 24px 36px 40px;
      display: grid;
      gap: 18px;
    }}
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
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
    .big {{
      font-size: 20px;
      font-weight: 600;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      font-weight: 600;
      font-size: 13px;
      letter-spacing: 0.3px;
    }}
    .status-pass {{ background: #e7f6ee; color: var(--ok); }}
    .status-drift {{ background: #fff2e5; color: var(--accent-2); }}
    .status-fail {{ background: #feecec; color: var(--fail); }}
    .status-unknown {{ background: #eef2f5; color: var(--muted); }}
    .muted {{ color: var(--muted); font-size: 14px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f3f5f7; }}
    .section-title {{ font-size: 18px; margin: 6px 0 8px; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .btn {{
      border: none;
      border-radius: 10px;
      padding: 8px 12px;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn-primary {{ background: var(--accent); color: #fff; }}
    .btn-warn {{ background: var(--accent-2); color: #fff; }}
    .btn-neutral {{ background: #eef4f6; color: var(--ink); }}
    .bar-track {{
      background: #e8edf2;
      border-radius: 6px;
      height: 10px;
      width: 100%;
      overflow: hidden;
    }}
    .bar {{
      height: 10px;
    }}
    .bar-pos {{ background: #2f855a; }}
    .bar-neg {{ background: #b45309; }}
    .highlight {{ color: var(--accent-2); font-weight: 700; }}
    .info-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #eef2f5;
      border: none;
      color: #6b7280;
      font-size: 12px;
      cursor: pointer;
      padding: 0;
      box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.06);
    }}
    .info-button::before {{ content: "i"; font-weight: 700; }}
    .tooltip {{
      position: relative;
      display: inline-flex;
      align-items: center;
    }}
    .tooltip-text {{
      position: absolute;
      right: 0;
      bottom: 26px;
      background: #1f2a33;
      color: #fff;
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 12px;
      white-space: nowrap;
      opacity: 0;
      transform: translateY(4px);
      transition: opacity 0.15s ease, transform 0.15s ease;
      pointer-events: none;
      z-index: 5;
    }}
    .tooltip:focus-within .tooltip-text,
    .tooltip:hover .tooltip-text {{
      opacity: 1;
      transform: translateY(0);
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    @media print {{
      body {{ margin: 0.5in; background: #fff; }}
      header {{ background: #fff; }}
      table {{ page-break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Drift Report</h1>
    <p>Harmony Bridge system-agnostic drift analysis</p>
  </header>
  <main>
    <div class="grid">
      <div class="card">
        <div class="label">Status</div>
        <div class="status-pill {status_class}">{status_value}</div>
        <div class="muted">{why_line or 'Why: n/a'}</div>
        <div class="muted">{no_metrics_hint}</div>
      </div>
      <div class="card">
        <div class="label">Run</div>
        <div class="big">{payload['run_id']}</div>
        <div class="muted">Baseline: {payload.get('baseline_run_id') or 'none'}</div>
      </div>
      <div class="card">
        <div class="label">Baseline Match</div>
        <div class="big">{match_line}</div>
        <div class="muted">{match_fields}</div>
      </div>
      <div class="card">
        <div class="card-head">
          <div class="label">Decision Basis</div>
          <span class="tooltip">
            <button class="info-button" type="button" aria-label="Decision basis details"></button>
            <span class="tooltip-text">{decision_basis_line}</span>
          </span>
        </div>
        <div class="big">{decision_basis_human}</div>
        <div class="muted">Context mismatch expected: {mismatch_expected}</div>
      </div>
    </div>

    <div class="card">
      <div class="label">Top Drivers</div>
      <div class="big">{top_drivers}</div>
      <div class="muted">Likely investigation areas: {", ".join(payload.get("likely_investigation_areas") or []) or "none"}</div>
      <div class="muted">Baseline reason: {baseline_reason} | Warning: {baseline_warning or 'none'}</div>
    </div>

    <div class="card">
      <div class="card-head">
        <div class="section-title">Feedback</div>
        <span class="tooltip">
          <button class="info-button" type="button" aria-label="Feedback privacy details"></button>
          <span class="tooltip-text">Sends anonymized decision metadata only (no logs or raw data).</span>
        </span>
      </div>
      <div class="muted">Start the Local Feedback Service (runs only on your machine): <code>bin/hb feedback serve</code></div>
      <div style="margin-top: 8px;">
        <label><input id="feedback-optin" type="checkbox" /> Enable feedback sending</label>
      </div>
      <div class="muted">Sends anonymized decision metadata only (no logs or raw data).</div>
      <div class="actions" style="margin-top: 10px;">
        <button class="btn btn-primary" onclick="sendFeedback('accepted')">Correct</button>
        <button class="btn btn-warn" onclick="sendFeedback('too_sensitive')">Too Sensitive</button>
        <button class="btn btn-warn" onclick="sendFeedback('missed_severity')">Missed Severity</button>
        <button class="btn btn-neutral" onclick="exportFeedback()">Export Feedback Summary</button>
      </div>
      <div style="margin-top: 8px;">
        <label>Note:</label>
        <input id="feedback-note" type="text" style="width: 60%;" />
      </div>
      <div style="margin-top: 6px;">
        <label>Time to resolution (minutes):</label>
        <input id="feedback-ttf" type="number" min="0" />
      </div>
      <div style="margin-top: 6px;">
        <label>Access token (optional):</label>
        <input id="feedback-token" type="password" />
      </div>
      <div id="feedback-status" class="muted" style="margin-top: 6px;"></div>
    </div>

    <div class="card">
      <div class="section-title">Drift Metrics</div>
      <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Baseline</th>
        <th>Current</th>
        <th>Delta</th>
        <th>Percent Change</th>
        <th>Threshold</th>
        <th>Percent Threshold</th>
        <th>Unit</th>
        <th>Severity</th>
        <th>Why Flagged</th>
      </tr>
    </thead>
    <tbody>
      {drift_table}
    </tbody>
      </table>
    </div>

    <div class="card">
      <div class="section-title">Diff Visualization</div>
      <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Baseline</th>
        <th>Current</th>
        <th>Delta</th>
        <th>Delta Magnitude</th>
      </tr>
    </thead>
    <tbody>
      {diff_table}
    </tbody>
      </table>
      <div class="muted">Bar length shows relative delta magnitude across flagged metrics.</div>
    </div>

    <div class="card">
      <div class="section-title">Distribution Drift</div>
      {dist_section}
    </div>

    <div class="card">
      <div class="section-title">Drift Attribution</div>
      <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Direction</th>
        <th>Effect</th>
        <th>Baseline Stats</th>
        <th>Current Stats</th>
        <th>Onset</th>
        <th>Sources</th>
        <th>Decision</th>
        <th>Evidence</th>
      </tr>
    </thead>
    <tbody>
      {attribution_table}
    </tbody>
      </table>
      <div class="muted">Legend: DRIFT = exceeds warn, below fail; FAIL = exceeds fail with persistence.</div>
      <div class="muted">Drift attribution is statistical, not causal.</div>
    </div>
  </main>
  <script>
    const feedbackBase = {feedback_payload_json};
    const optinKey = 'hb_feedback_optin';
    const optinCheckbox = document.getElementById('feedback-optin');
    const storedOptin = localStorage.getItem(optinKey);
    if (storedOptin !== null) {{
      optinCheckbox.checked = storedOptin === 'true';
    }}
    optinCheckbox.addEventListener('change', () => {{
      localStorage.setItem(optinKey, optinCheckbox.checked ? 'true' : 'false');
    }});
    function sendFeedback(action) {{
      if (!optinCheckbox.checked) {{
        document.getElementById('feedback-status').textContent = 'Enable feedback sending to submit.';
        return;
      }}
      const note = document.getElementById('feedback-note').value;
      const ttf = document.getElementById('feedback-ttf').value;
      const token = document.getElementById('feedback-token').value;
      const headers = {{'Content-Type': 'application/json'}};
      if (token) {{
        headers['X-HB-Token'] = token;
      }}
      const payload = Object.assign({{}}, feedbackBase, {{
        operator_action: action,
        operator_note: note || null,
        time_to_resolution_minutes: ttf ? parseInt(ttf, 10) : null
      }});
      fetch('http://127.0.0.1:8765/feedback', {{
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      }}).then(resp => resp.json()).then(data => {{
        document.getElementById('feedback-status').textContent = 'Feedback saved.';
      }}).catch(err => {{
        document.getElementById('feedback-status').textContent = 'Feedback failed (start server).';
      }});
    }}
    function exportFeedback() {{
      const token = document.getElementById('feedback-token').value;
      const headers = {{}};
      if (token) {{
        headers['X-HB-Token'] = token;
      }}
      fetch('http://127.0.0.1:8765/export?mode=summary', {{ headers }}).then(resp => resp.json()).then(data => {{
        const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'hb_feedback_summary.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        document.getElementById('feedback-status').textContent = 'Feedback summary downloaded.';
      }}).catch(() => {{
        document.getElementById('feedback-status').textContent = 'Export failed (start server).';
      }});
    }}
  </script>
</body>
</html>
"""
    with open(html_path, "w") as f:
        f.write(html_doc)
    return json_path, html_path


def write_pdf(html_path, pdf_path):
    tool = shutil.which("wkhtmltopdf")
    if tool is None:
        return _write_pdf_pure_python(html_path, pdf_path)
    try:
        subprocess.run([tool, html_path, pdf_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        return None, f"pdf export failed: {exc}"
    return pdf_path, None


def _write_pdf_pure_python(html_path, pdf_path):
    try:
        from fpdf import FPDF
    except ImportError as exc:
        return None, "wkhtmltopdf not found and fpdf2 is not installed"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    with open(html_path, "r") as f:
        text = f.read()

    # Minimal HTML stripping for a readable PDF.
    text = (
        text.replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
    )
    for token in ["<td>", "</td>", "<tr>", "</tr>", "<th>", "</th>"]:
        text = text.replace(token, " ")
    for token in ["<table>", "</table>", "<thead>", "</thead>", "<tbody>", "</tbody>"]:
        text = text.replace(token, "\n")
    for token in ["<h1>", "</h1>", "<h2>", "</h2>", "<div>", "</div>"]:
        text = text.replace(token, "\n")
    import re

    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        pdf.multi_cell(0, 5, line)
    pdf.output(pdf_path)
    return pdf_path, None
