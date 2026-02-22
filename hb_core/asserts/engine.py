import yaml
from datetime import datetime, timezone


def load_asserts(path):
    with open(path, "r") as f:
        payload = yaml.safe_load(f) or {}
    return payload.get("asserts", [])


def _compare(op, actual, expected):
    if op == "<":
        return actual < expected
    if op == "<=":
        return actual <= expected
    if op == ">":
        return actual > expected
    if op == ">=":
        return actual >= expected
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    raise ValueError(f"unsupported op: {op}")


def evaluate_asserts(asserts, metrics_map, run_id=None):
    """Evaluate assertion rules. Each result includes timestamp_utc and, on FAIL, offending_segment (RITS-style evidence capture)."""
    results = []
    ts = datetime.now(timezone.utc).isoformat()
    for rule in asserts:
        rule_id = rule.get("id") or rule.get("name") or "assert"
        metric = rule.get("metric")
        op = rule.get("op")
        expected = rule.get("value")
        severity = (rule.get("severity") or "fail").lower()
        base = {"id": rule_id, "metric": metric, "timestamp_utc": ts}
        if run_id is not None:
            base["run_id"] = run_id
        if not metric or not op:
            results.append({**base, "status": "NO_TEST", "reason": "missing metric/op"})
            continue
        actual = metrics_map.get(metric)
        if actual is None:
            results.append({**base, "status": "NO_TEST", "reason": "metric missing"})
            continue
        try:
            passed = _compare(op, actual, expected)
        except Exception as exc:
            results.append({**base, "status": "NO_TEST", "reason": f"compare error: {exc}"})
            continue
        status = "PASS" if passed else "FAIL"
        out = {
            **base,
            "op": op,
            "expected": expected,
            "actual": actual,
            "severity": severity,
            "status": status,
        }
        if status == "FAIL":
            out["offending_segment"] = {"actual": actual, "expected": expected, "op": op, "metric": metric}
        results.append(out)
    return results
