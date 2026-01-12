import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyze import (
    compute_run_id,
    compare_metrics,
    load_metrics_csv,
    load_metrics_log,
    normalize_metric_value,
    render_report,
    summarize,
)
from registry_cli import write_trend

import tempfile
import sqlite3


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.baseline_csv = os.path.join(root, "runs", "baseline", "baseline-run.csv")
        self.current_csv = os.path.join(root, "runs", "current", "current-run.csv")
        self.baseline_log = os.path.join(root, "runs", "baseline", "baseline-run.log")
        self.thresholds = {"reset_count": {"drift_threshold": 1}}
        self.config = os.path.join(root, "config", "thresholds.yaml")

    def test_load_metrics_csv(self):
        metrics = load_metrics_csv(self.baseline_csv)
        self.assertEqual(metrics["reset_count"], (0, None))
        self.assertEqual(metrics["avg_latency_ms"], (12.4, None))

    def test_load_metrics_log(self):
        metrics = load_metrics_log(self.baseline_log)
        self.assertEqual(metrics["error_code_frequency"], (0.01, None))

    def test_compare_and_summarize(self):
        baseline = load_metrics_csv(self.baseline_csv)
        current = load_metrics_csv(self.current_csv)
        comparison = compare_metrics(baseline, current, self.thresholds)
        summary = summarize(comparison)
        self.assertEqual(summary, "PASS-with-drift")

    def test_compute_run_id_deterministic(self):
        first = compute_run_id(self.current_csv, self.baseline_csv, self.config)
        second = compute_run_id(self.current_csv, self.baseline_csv, self.config)
        self.assertEqual(first, second)

    def test_unit_normalization(self):
        thresholds = {
            "avg_latency_ms": {
                "unit": "ms",
                "unit_map": {"s": 1000, "ms": 1, "us": 0.001},
            }
        }
        value, unit = normalize_metric_value("avg_latency_ms", (1.2, "s"), thresholds)
        self.assertEqual(unit, "ms")
        self.assertAlmostEqual(value, 1200.0)

    def test_golden_report_snapshot(self):
        baseline = {
            "reset_count": (0, None),
            "watchdog_triggers": (0, None),
            "error_count": (2, None),
        }
        current = {
            "reset_count": (3, None),
            "watchdog_triggers": (0, None),
            "error_count": (2, None),
        }
        thresholds = {
            "reset_count": {"drift_threshold": 1},
            "error_count": {"drift_threshold": 0},
        }
        comparison = compare_metrics(baseline, current, thresholds)
        summary = summarize(comparison)
        drift_count = sum(1 for m in comparison if m["status"] == "drift")
        report = render_report(
            "run-001",
            "base-001",
            summary,
            comparison,
            drift_count,
            "config-001",
            thresholds,
            "default",
        )

        golden_path = os.path.join(
            os.path.dirname(__file__), "golden", "run-report.html"
        )
        with open(golden_path, "r") as f:
            golden = f.read()
        self.assertEqual(report, golden)

    def test_golden_trend_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "runs.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE runs (
                    run_id TEXT PRIMARY KEY,
                    baseline_id TEXT,
                    run_path TEXT,
                    baseline_path TEXT,
                    config_path TEXT,
                    summary TEXT,
                    metrics_count INTEGER,
                    drift_count INTEGER,
                    created_at TEXT,
                    report_dir TEXT,
                    report_path TEXT,
                    diff_path TEXT,
                    summary_path TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, baseline_id, run_path, baseline_path, config_path, summary,
                    metrics_count, drift_count, created_at, report_dir, report_path,
                    diff_path, summary_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "run-001",
                    "base-001",
                    "/runs/current.csv",
                    "/runs/baseline.csv",
                    "/config/thresholds.yaml",
                    "PASS-with-drift",
                    7,
                    2,
                    "2025-01-01T00:00:00+00:00",
                    "/reports/run-001",
                    "/reports/run-001/run-report.html",
                    "/reports/run-001/run-diff.json",
                    "/reports/run-001/run-summary.txt",
                ),
            )
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, baseline_id, run_path, baseline_path, config_path, summary,
                    metrics_count, drift_count, created_at, report_dir, report_path,
                    diff_path, summary_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "run-000",
                    "base-000",
                    "/runs/current-old.csv",
                    "/runs/baseline.csv",
                    "/config/thresholds.yaml",
                    "PASS",
                    7,
                    0,
                    "2024-12-31T00:00:00+00:00",
                    "/reports/run-000",
                    "/reports/run-000/run-report.html",
                    "/reports/run-000/run-diff.json",
                    "/reports/run-000/run-summary.txt",
                ),
            )
            conn.commit()
            out_path = os.path.join(tmpdir, "trend.html")
            write_trend(conn, out_path, 50)
            with open(out_path, "r") as f:
                trend = f.read()

        golden_path = os.path.join(
            os.path.dirname(__file__), "golden", "trend-report.html"
        )
        with open(golden_path, "r") as f:
            golden = f.read()
        self.assertEqual(trend, golden)


if __name__ == "__main__":
    unittest.main()
