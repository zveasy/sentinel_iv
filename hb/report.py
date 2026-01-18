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
    for item in payload.get("top_drifts", payload.get("drift_metrics", [])):
        drift_rows.append(
            "<tr>"
            f"<td>{item['metric']}</td>"
            f"<td>{item['baseline']}</td>"
            f"<td>{item['current']}</td>"
            f"<td>{item['delta']}</td>"
            f"<td>{item.get('percent_change')}</td>"
            f"<td>{item.get('drift_threshold')}</td>"
            f"<td>{item.get('drift_percent')}</td>"
            f"<td>{item.get('unit') or ''}</td>"
            f"<td>{item.get('severity') or ''}</td>"
            f"<td>{_narrative(item)}</td>"
            "</tr>"
        )
    drift_table = "\n".join(drift_rows)

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
    dist_table = "\n".join(dist_rows) if dist_rows else "<tr><td colspan=\"6\">none</td></tr>"

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
        onset_text = "Onset (approx): n/a"
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

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Harmony Bridge Drift Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f3f3; }}
    @media print {{
      body {{ margin: 0.5in; }}
      table {{ page-break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <h1>Drift Report</h1>
  <div>Status: {payload['status']}</div>
  <div>Run ID: {payload['run_id']}</div>
  <div>Baseline Run ID: {payload.get('baseline_run_id') or 'none'}</div>
  <div>Baseline Reason: {baseline_reason}</div>
  <div>Baseline Match Level: {match_line}</div>
  <div>Baseline Match Fields: {match_fields}</div>
  <div>Context Mismatch Expected: {mismatch_expected}</div>
  <div>Baseline Warning: {baseline_warning or 'none'}</div>
  <div>Top Drivers: {top_drivers}</div>
  <div>Decision Basis: {decision_basis_line}</div>
  <div>{why_line or 'Why: n/a'}</div>
  <div>Likely Investigation Areas: {", ".join(payload.get("likely_investigation_areas") or []) or "none"}</div>
  <h2>Drift Metrics</h2>
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
  <h2>Distribution Drift</h2>
  <table>
    <thead>
      <tr>
        <th>Metric</th>
        <th>Method</th>
        <th>Statistic</th>
        <th>Threshold</th>
        <th>Baseline Samples</th>
        <th>Current Samples</th>
      </tr>
    </thead>
    <tbody>
      {dist_table}
    </tbody>
  </table>
  <h2>Drift Attribution</h2>
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
  <div>Legend: DRIFT = exceeds warn, below fail; FAIL = exceeds fail with persistence.</div>
  <div>Drift attribution is statistical, not causal.</div>
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
