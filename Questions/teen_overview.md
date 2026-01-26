# Project overview (teen-friendly)

Imagine you have two screenshots of your grades from last month and this month. This project is like a super picky friend who compares them and tells you what changed, what looks weird, and what might need attention.

Here is the big idea:
- You collect metrics (numbers) about a system or test run.
- You compare today (current run) against yesterday (baseline run).
- The system highlights big changes (drift), serious problems (fail), and missing info (warnings).
- It outputs a report you can read (HTML/JSON).

How it works step by step (more detail):
1) A run produces an artifact folder with `metrics.csv` and `run_meta.json`.
2) The system loads the metric registry (the rulebook) so it knows which metrics exist and their thresholds.
3) It normalizes metric names (aliases) and units so comparisons are fair.
4) A baseline run is picked (usually the last PASS with similar context like environment/mode).
5) For each metric, it checks:
   - Is the metric missing? If yes, add a warning.
   - What is the delta (current - baseline)?
   - What is the percent change (delta / baseline)?
6) If the change crosses drift_threshold (absolute) or drift_percent (relative), it becomes drift.
7) If the metric is marked critical and exceeds fail_threshold (or breaks an invariant rule), it becomes fail.
8) If sample lists are available, it can run distribution drift (like a KS test) and compute confidence.
9) It ranks the top drivers by size of change (z-score, then percent, then delta).
10) It builds a report with:
   - Status (PASS, PASS_WITH_DRIFT, FAIL, NO_TEST)
   - Warnings and fail metrics
   - Top drivers and “why” text
   - Decision basis (what rule got triggered)

Key terms in teen language:
- Registry: The rulebook. It lists the metrics we care about and their limits.
- Baseline: The "before" snapshot we compare to.
- Drift: A big change from baseline (like your grade jumping or dropping a lot).
- Warnings: Missing or weird info that prevents good comparison.
- Fail: A serious issue that breaks a rule.
- Coverage: How much of the expected data actually showed up.
- Deep drift: Extra checks using samples, like comparing two piles of numbers in more detail.

What you get at the end:
- A status: PASS, PASS_WITH_DRIFT, FAIL, or NO_TEST.
- A report showing top changes and what likely caused them.
- A list of warnings and fails so you can fix missing or broken data.

Why this is useful:
- It catches unexpected changes early.
- It helps you explain what changed and why.
- It gives a consistent, repeatable way to judge runs.
