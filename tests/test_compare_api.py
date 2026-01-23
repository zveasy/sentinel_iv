import json
import os

from hb_core.compare import run_compare


def _case_dir(case_name):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(root, "samples", "cases", case_name)


def _load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def _run_compare_case(tmp_path, case_name, monkeypatch):
    case_dir = _case_dir(case_name)
    baseline_source = os.path.join(case_dir, "baseline_source.csv")
    current_source = os.path.join(case_dir, "current_source.csv")
    baseline_meta = os.path.join(case_dir, "baseline_run_meta.json")
    current_meta = os.path.join(case_dir, "current_run_meta.json")

    run_meta = {
        "baseline": _load_json(baseline_meta),
        "current": _load_json(current_meta),
    }

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    monkeypatch.setenv("HB_COMPARE_SOURCE", "pba_excel")
    monkeypatch.setenv("HB_METRIC_REGISTRY", os.path.join(root, "metric_registry.yaml"))
    monkeypatch.setenv("HB_BASELINE_POLICY", os.path.join(root, "baseline_policy.yaml"))

    out_dir = tmp_path / "compare_out"
    return run_compare(
        baseline_path=baseline_source,
        run_path=current_source,
        out_dir=str(out_dir),
        schema_mode=None,
        schema_path=None,
        thresholds_path=os.path.join(root, "baseline_policy.yaml"),
        run_meta=run_meta,
    )


def test_run_compare_pass(tmp_path, monkeypatch):
    result = _run_compare_case(tmp_path, "no_drift_pass", monkeypatch)
    assert result.status == "PASS"
    assert os.path.exists(result.report_path)
    assert os.path.exists(result.summary_path)


def test_run_compare_drift(tmp_path, monkeypatch):
    result = _run_compare_case(tmp_path, "single_metric_drift", monkeypatch)
    assert result.status in {"PASS_WITH_DRIFT", "FAIL"}
    assert os.path.exists(result.report_path)
