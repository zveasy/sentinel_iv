import json
import os
import time
import io
from argparse import Namespace
from contextlib import redirect_stdout

import pytest

from hb import cli
from hb.adapters import pba_excel_adapter
from hb import registry


def _case_dir(case_name):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(root, "samples", "cases", case_name)


def _load_expected(case_name):
    with open(os.path.join(_case_dir(case_name), "expected.json"), "r") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "case_name",
    [
        "no_drift_pass",
        "single_metric_drift",
        "multi_metric_drift",
        "reset_triggered_fail",
        "missing_metric_warn",
        "header_alias_change",
        "unit_conversion_ms_us",
        "baseline_missing_fallback",
        "distribution_drift",
    ],
)
def test_cases(tmp_path, case_name):
    case_dir = _case_dir(case_name)
    baseline_source = os.path.join(case_dir, "baseline_source.csv")
    current_source = os.path.join(case_dir, "current_source.csv")
    baseline_meta = os.path.join(case_dir, "baseline_run_meta.json")
    current_meta = os.path.join(case_dir, "current_run_meta.json")

    db_path = os.path.join(tmp_path, "runs.db")
    reports_dir = os.path.join(tmp_path, "reports")
    runs_dir = os.path.join(tmp_path, "runs")

    ingest_args = Namespace(
        source="pba_excel",
        path=baseline_source,
        run_meta=baseline_meta,
        out=os.path.join(runs_dir, "baseline"),
        metric_registry=os.path.join(os.path.dirname(__file__), "..", "metric_registry.yaml"),
    )
    baseline_run_dir = cli.ingest(ingest_args)

    analyze_args = Namespace(
        run=baseline_run_dir,
        baseline_policy=os.path.join(os.path.dirname(__file__), "..", "baseline_policy.yaml"),
        metric_registry=os.path.join(os.path.dirname(__file__), "..", "metric_registry.yaml"),
        db=db_path,
        reports=reports_dir,
        top=5,
        redaction_policy=None,
    )
    cli.analyze(analyze_args)

    ingest_args.path = current_source
    ingest_args.run_meta = current_meta
    ingest_args.out = os.path.join(runs_dir, "current")
    current_run_dir = cli.ingest(ingest_args)

    analyze_args.run = current_run_dir
    report_dir = cli.analyze(analyze_args)

    report_path = os.path.join(report_dir, "drift_report.json")
    with open(report_path, "r") as f:
        report = json.load(f)

    expected = _load_expected(case_name)
    assert report["status"] == expected["status"]
    if report["status"] != "PASS":
        attribution = report.get("drift_attribution", {}).get("top_drivers", [])
        assert attribution, "expected drift attribution when status != PASS"

    if "drift_metrics_count" in expected:
        assert len(report["drift_metrics"]) == expected["drift_metrics_count"]
    if "drift_metrics" in expected:
        metrics = [item["metric"] for item in report["drift_metrics"]]
        for metric in expected["drift_metrics"]:
            assert metric in metrics
    if "fail_metrics" in expected:
        for metric in expected["fail_metrics"]:
            assert metric in report.get("fail_metrics", [])
    if "warnings_contains" in expected:
        for warning in expected["warnings_contains"]:
            assert warning in report.get("warnings", [])
    if "baseline_reason" in expected:
        assert report.get("baseline_reason") == expected["baseline_reason"]
    if "distribution_drifts_count" in expected:
        assert len(report.get("distribution_drifts", [])) == expected["distribution_drifts_count"]


def test_streaming_excel_unit_sheet():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sample = os.path.join(root, "samples", "pba_unit_sheet_example.xlsx")
    metrics = pba_excel_adapter.parse_stream(sample)
    assert "avg_latency_ms" in metrics
    assert metrics["avg_latency_ms"]["unit"] == "ms"


def test_streaming_benchmark_threshold():
    bench_file = os.environ.get("HB_BENCH_FILE")
    max_seconds = os.environ.get("HB_BENCH_MAX_S")
    if not bench_file or not max_seconds:
        pytest.skip("HB_BENCH_FILE or HB_BENCH_MAX_S not set")
    max_seconds = float(max_seconds)
    start = time.time()
    pba_excel_adapter.parse_stream(bench_file)
    elapsed = time.time() - start
    assert elapsed <= max_seconds, f"streaming took {elapsed:.3f}s, max {max_seconds}s"


def test_schema_unknown_columns_warn(tmp_path):
    data = "Metric,Current,Extra\navg_latency_ms,10,foo\n"
    csv_path = tmp_path / "unknown_cols.csv"
    csv_path.write_text(data)
    buf = io.StringIO()
    with redirect_stdout(buf):
        metrics = pba_excel_adapter.parse(str(csv_path))
    output = buf.getvalue()
    assert "unknown columns ignored" in output
    assert "avg_latency_ms" in metrics


def test_schema_missing_required_fails(tmp_path):
    data = "Current\n10\n"
    csv_path = tmp_path / "missing_required.csv"
    csv_path.write_text(data)
    with pytest.raises(ValueError, match="missing required columns"):
        pba_excel_adapter.parse(str(csv_path))


def test_schema_alias_column(tmp_path, monkeypatch):
    schema = (
        "source: pba_excel\n"
        "allow_extra_columns: true\n"
        "required_columns:\n"
        "  - metric\n"
        "optional_columns:\n"
        "  - current\n"
        "either_current_or_value: true\n"
        "aliases:\n"
        "  current: [CurrentValue]\n"
    )
    schema_path = tmp_path / "pba_schema.yaml"
    schema_path.write_text(schema)
    monkeypatch.setenv("HB_SCHEMA_PBA_EXCEL", str(schema_path))

    data = "Metric,CurrentValue\navg_latency_ms,10\n"
    csv_path = tmp_path / "alias_cols.csv"
    csv_path.write_text(data)
    metrics = pba_excel_adapter.parse(str(csv_path))
    assert "avg_latency_ms" in metrics


def test_schema_alias_with_unknown_columns_warns(tmp_path, monkeypatch):
    schema = (
        "source: pba_excel\n"
        "allow_extra_columns: true\n"
        "required_columns:\n"
        "  - metric\n"
        "optional_columns:\n"
        "  - current\n"
        "either_current_or_value: true\n"
        "aliases:\n"
        "  current: [CurrentValue]\n"
    )
    schema_path = tmp_path / "pba_schema.yaml"
    schema_path.write_text(schema)
    monkeypatch.setenv("HB_SCHEMA_PBA_EXCEL", str(schema_path))

    data = "Metric,CurrentValue,ExtraCol\navg_latency_ms,10,ignored\n"
    csv_path = tmp_path / "alias_unknown.csv"
    csv_path.write_text(data)
    buf = io.StringIO()
    with redirect_stdout(buf):
        metrics = pba_excel_adapter.parse(str(csv_path))
    output = buf.getvalue()
    assert "unknown columns ignored" in output
    assert "avg_latency_ms" in metrics


def test_schema_disallow_extra_columns_fails(tmp_path, monkeypatch):
    schema = (
        "source: pba_excel\n"
        "allow_extra_columns: false\n"
        "required_columns:\n"
        "  - metric\n"
        "optional_columns:\n"
        "  - current\n"
        "either_current_or_value: true\n"
    )
    schema_path = tmp_path / "pba_schema.yaml"
    schema_path.write_text(schema)
    monkeypatch.setenv("HB_SCHEMA_PBA_EXCEL", str(schema_path))

    data = "Metric,Current,ExtraCol\navg_latency_ms,10,ignored\n"
    csv_path = tmp_path / "extra_cols.csv"
    csv_path.write_text(data)
    with pytest.raises(ValueError, match="unknown columns"):
        pba_excel_adapter.parse(str(csv_path))


def test_baseline_request_approve_flow(tmp_path):
    case_dir = _case_dir("no_drift_pass")
    baseline_source = os.path.join(case_dir, "baseline_source.csv")
    baseline_meta = os.path.join(case_dir, "baseline_run_meta.json")

    db_path = os.path.join(tmp_path, "runs.db")
    reports_dir = os.path.join(tmp_path, "reports")
    runs_dir = os.path.join(tmp_path, "runs")
    metric_registry = os.path.join(os.path.dirname(__file__), "..", "metric_registry.yaml")

    ingest_args = Namespace(
        source="pba_excel",
        path=baseline_source,
        run_meta=baseline_meta,
        out=os.path.join(runs_dir, "baseline"),
        metric_registry=metric_registry,
    )
    baseline_run_dir = cli.ingest(ingest_args)

    analyze_args = Namespace(
        run=baseline_run_dir,
        baseline_policy=os.path.join(os.path.dirname(__file__), "..", "baseline_policy.yaml"),
        metric_registry=metric_registry,
        db=db_path,
        reports=reports_dir,
        top=5,
        redaction_policy=None,
    )
    cli.analyze(analyze_args)

    with open(baseline_meta, "r") as f:
        run_id = json.load(f)["run_id"]

    policy_path = os.path.join(tmp_path, "baseline_policy.yaml")
    with open(policy_path, "w") as f:
        f.write(
            "baseline_policy:\n"
            "  strategy: last_pass\n"
            "  fallback: latest\n"
            "  warn_on_mismatch: true\n"
            "  tag:\n"
            "  governance:\n"
            "    require_approval: true\n"
            "    approvals_required: 1\n"
            "    approvers: [alice]\n"
        )

    request_args = Namespace(
        run_id=run_id,
        tag="golden",
        requested_by="bob",
        reason="test request",
        request_id=None,
        db=db_path,
    )
    cli.baseline_request(request_args)

    approve_args = Namespace(
        run_id=run_id,
        tag="golden",
        approved_by="alice",
        reason="approved",
        approval_id=None,
        request_id=None,
        metric_registry=metric_registry,
        db=db_path,
        baseline_policy=policy_path,
    )
    cli.baseline_approve(approve_args)

    conn = registry.init_db(db_path)
    tags = registry.list_baseline_tags(conn)
    assert any(tag == "golden" and tag_run_id == run_id for tag, tag_run_id, *_ in tags)
