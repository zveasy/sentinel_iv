# Questions and Answers


# 1. What are bytes and how do they relate to report in terms of detecting drift?
Answer: The baseline/run byte counts are file-size metadata collected during compare runs (e.g., baseline_bytes/run_bytes). They are stored for performance/metadata tracking and are not used in drift calculations; drift is computed from metric values and samples, not file size.

# 2. How do we determine if a report is valid?
Answer: A report is valid if its underlying artifact directory validates (run_meta.json exists with required fields, metrics.csv exists, is non-empty, and has metric/value columns) and the report JSON can be loaded without errors. Optional signals/events files must also be well-formed when present.

# 3. How doe we determine Sample Sufficiency?
Answer: Sample sufficiency is derived from sample counts in metric tags. The engine labels confidence as high (>=200), medium (>=50), low (>0), or n/a. The combined report rolls this into a single label by averaging top-driver confidence.

# 4. What does Avg Drift Score mean?
Answer: In combined reports, Avg Drift Score is the mean of per-run drift scores, where each drift score comes from the top driver (decision_basis.drift_score if present, otherwise the top driver score).

# 5. How can we find and locate what are the warnings and errors for a report?
Answer: Open the report JSON (`drift_report.json`) and look at `warnings` and `fail_metrics`. The HTML report also surfaces these in the report tables and summary sections.

# 6. How is Warnings / Fails calculated?
Answer: For combined reports, it is the count of warning strings plus the count of fail metrics for each run (and summed across runs for the summary). Warnings come from missing metrics or early-exit messages; fails come from critical thresholds or invariant violations.

# 7. How is the Final Score calculated?
Answer: There is no separate "final score" in the report logic. The overall outcome is the status (PASS, PASS_WITH_DRIFT, FAIL, NO_TEST). The numeric score shown in some summaries is the top-driver drift_score (abs(zscore) else abs(percent) else abs(delta)), and combined reports average those.

# 8. How is coverage calculated?
Answer: Coverage is derived from the metric registry size minus missing-current-metric warnings: (registry_total - missing_current) / registry_total * 100. In combined reports it averages that per-run coverage.
Subpoint: More generally, coverage is a completeness signal for how many expected metrics were present in the current run; it does not reflect drift severity, only whether the current metrics are available for evaluation.
Sub-bullets:
- Registry is non-empty, but every expected metric is missing in the current run, so missing_current equals registry_total.
- The current artifact has metrics that do not map to the registry (unknown metrics), so none of the expected metrics are counted as present.
- The report is computed against a registry that does not match the run context (wrong registry file or schema), causing all expected metrics to be treated as missing.

# 9. What is deep drift?
Answer: Deep drift refers to distribution drift checks on sample data (e.g., KS statistic over samples). If distribution drift is enabled and sample lists exist, the report includes `distribution_drifts`, and combined reports show Deep Drift as on.

# 10. How is the final verdict determined?
Answer: Status is FAIL if any critical metric or invariant fails; PASS_WITH_DRIFT if any drift or distribution drift is present; otherwise PASS. In plan runs, assert results are merged so any assert FAIL forces FAIL, and NO_TEST can override PASS if no asserts ran.

# 11. Top Recurring Drivers how are they calculated and what are they?
Answer: In combined reports, recurring drivers are counted from drift metrics and fail metrics across runs, then the top 5 by frequency are shown. They highlight the most frequently problematic metrics.

# 12. How are the drivers ranked?
Answer: Drivers are sorted by absolute score (abs(zscore), else abs(percent), else abs(delta); KS stat can also set a score). Ties are broken deterministically when enabled.

# 13. How are the drivers filtered?
Answer: Only flagged metrics are kept: those with drift, fail, or distribution drift. Unflagged metrics are filtered out of top driver lists.

# 14. Based on status for example: 1 increased by 147.41% (75.9843) exceeding warn threshold 0.1 for 5 consecutive cycles. How is this calculated and what does it mean?
Answer: The report constructs this from the top driver: the percent change and delta come from the driver effect size, the warn threshold comes from the drift threshold/percent, and persistence cycles come from the drift_persistence setting (default 5). It means the top metric exceeded its warn threshold consistently across that many samples.
Subpoint: It is not a target being met; it is a change relative to the baseline value. The metric moved +147.41% vs baseline (and by +75.9843 in absolute terms), which exceeded the warn threshold for the configured number of consecutive cycles.

# 15. Distribution drift?
Answer: Distribution drift is detected with a KS test when both baseline and current metrics include sample lists. If the KS statistic exceeds the configured threshold, the metric appears in `distribution_drifts`.

# 16. What makes a metric show up in fail_metrics?
Answer: A metric is added to fail_metrics if it is marked critical and exceeds its fail_threshold (or >0 when no fail_threshold is set), or if it violates invariant rules (invariant_min/max/eq).

# 17. What is the decision basis shown in reports?
Answer: Decision basis records why a driver was flagged (drift_threshold, drift_percent, critical, distribution_ks) plus its score type and thresholds; the report surfaces these details in the Decision Basis card and tooltips.

# 18. What is the difference between drift_threshold and drift_percent?
Answer: drift_threshold is an absolute delta check; drift_percent is a percent change check relative to baseline (when baseline is non-zero). A min_effect can suppress tiny changes even if thresholds are exceeded.

# 19. What do "missing current metric" and "missing baseline metric" warnings mean?
Answer: They indicate that a metric was expected (per registry or comparison set) but not present in the current or baseline artifact, so drift cannot be computed for that metric.

# 20. What is drift persistence and where does it come from?
Answer: Drift persistence is the number of consecutive samples required to treat drift as sustained. It comes from metric config drift_persistence (default 5) and appears in driver attribution and report text.

# 21. What does baseline match level/score mean?
Answer: Baseline matching compares context fields (environment, scenario_id, etc.). The score is the number of matched fields out of possible, and the level is HIGH/MED/LOW/NONE based on that ratio.

# 22. What does NO_METRICS mean?
Answer: It means no metrics were evaluated (empty inputs or missing mappings). The engine emits a warning and returns status NO_METRICS.

# 23. Where do I find the report outputs?
Answer: Report outputs are written to a report directory as `drift_report.json` and `drift_report.html`. In compare runs, this lives under the output reports directory; in plan runs, each scenario writes under the plan output results folder.

# 24. What data is used for distribution drift and onset evidence?
Answer: The engine uses sample lists provided in metric tags (`tags.samples`). Those samples drive KS checks, onset/evidence windows, and confidence labels.

# 25. What is the registry and how should I think about it?
Answer:
- The registry is the catalog of expected metrics and their configs (thresholds, invariants, units, optional distribution drift settings).
- It defines what the system will look for in a run and how drift/FAIL is evaluated for each metric.
- It is separate from baselines; baselines supply the historical values, while the registry supplies the rules and expected metric names.
Sub-bullets:
- Where it lives: typically `metric_registry.yaml`.
- Why it matters: coverage and missing-metric warnings are computed against it.
- When it causes issues: a mismatched registry or schema can make valid run metrics appear \"missing\".
