import json

from hb.registry_utils import normalize_alias


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def _unit_convert(value, unit, metric_config):
    if value is None:
        return None, unit
    unit_map = metric_config.get("unit_map") or {}
    canonical = metric_config.get("unit")
    if unit is None:
        return value, canonical
    normalized = normalize_alias(str(unit))
    if normalized in unit_map:
        return value * unit_map[normalized], canonical
    return value, unit


def normalize_metrics(raw_metrics, metric_registry):
    alias_index = metric_registry["alias_index"]
    normalized = {}
    warnings = []
    for name, data in raw_metrics.items():
        alias_key = normalize_alias(name)
        if alias_key not in alias_index:
            warnings.append(f"unknown metric: {name}")
            continue
        canonical = alias_index[alias_key]
        config = metric_registry["metrics"].get(canonical, {})
        value = _to_float(data.get("value"))
        unit = data.get("unit")
        value, unit = _unit_convert(value, unit, config)
        normalized[canonical] = {
            "value": value,
            "unit": unit,
            "tags": data.get("tags"),
        }
    return normalized, sorted(warnings)


def _extract_samples(metric):
    tags = metric.get("tags")
    if not tags:
        return None
    if isinstance(tags, dict):
        samples = tags.get("samples")
    else:
        try:
            parsed = json.loads(tags)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, dict):
            return None
        samples = parsed.get("samples")
    if not isinstance(samples, list):
        return None
    cleaned = []
    for value in samples:
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    return cleaned or None


def _ks_statistic(sample_a, sample_b):
    a = sorted(sample_a)
    b = sorted(sample_b)
    if not a or not b:
        return None
    i = 0
    j = 0
    n = len(a)
    m = len(b)
    d = 0.0
    while i < n and j < m:
        if a[i] <= b[j]:
            i += 1
        else:
            j += 1
        cdf_a = i / n
        cdf_b = j / m
        d = max(d, abs(cdf_a - cdf_b))
    return d


def compare_metrics(current, baseline, metric_registry, distribution_enabled=True):
    drift = []
    warnings = []
    fail = []
    invariant_violations = []
    distribution_drifts = []
    all_metrics = sorted(set(current.keys()) | set(baseline.keys()))
    for metric in all_metrics:
        config = metric_registry["metrics"].get(metric, {})
        cur = current.get(metric)
        base = baseline.get(metric)
        if cur is None or cur.get("value") is None:
            warnings.append(f"missing current metric: {metric}")
            continue
        invariant_min = config.get("invariant_min")
        invariant_max = config.get("invariant_max")
        invariant_eq = config.get("invariant_eq")
        violated = False
        if invariant_eq is not None and cur["value"] != invariant_eq:
            violated = True
        if invariant_min is not None and cur["value"] < invariant_min:
            violated = True
        if invariant_max is not None and cur["value"] > invariant_max:
            violated = True
        if violated:
            invariant_violations.append(
                {
                    "metric": metric,
                    "current": cur["value"],
                    "invariant_min": invariant_min,
                    "invariant_max": invariant_max,
                    "invariant_eq": invariant_eq,
                }
            )
            fail.append(metric)
        if config.get("critical"):
            fail_threshold = config.get("fail_threshold")
            if fail_threshold is None and cur["value"] > 0:
                fail.append(metric)
            elif fail_threshold is not None and cur["value"] > fail_threshold:
                fail.append(metric)

        if base is None or base.get("value") is None:
            warnings.append(f"missing baseline metric: {metric}")
            continue
        delta = cur["value"] - base["value"]
        percent = None
        if base["value"] != 0:
            percent = (delta / base["value"]) * 100.0

        drift_threshold = config.get("drift_threshold")
        drift_percent = config.get("drift_percent")
        min_effect = config.get("min_effect")
        is_drift = False
        if drift_threshold is not None and abs(delta) > drift_threshold:
            is_drift = True
        if drift_percent is not None and percent is not None and abs(percent) > drift_percent:
            is_drift = True
        if is_drift and min_effect is not None and abs(delta) < min_effect:
            is_drift = False

        if is_drift:
            severity = "FAIL" if metric in fail else "DRIFT"
            drift.append(
                {
                    "metric": metric,
                    "baseline": base["value"],
                    "current": cur["value"],
                    "delta": delta,
                    "percent_change": percent,
                    "drift_threshold": drift_threshold,
                    "drift_percent": drift_percent,
                    "min_effect": min_effect,
                    "unit": cur.get("unit") or base.get("unit"),
                    "severity": severity,
                }
            )

        dist_cfg = config.get("distribution_drift") or {}
        if not distribution_enabled:
            dist_cfg = {}
        if dist_cfg:
            cur_samples = _extract_samples(cur)
            base_samples = _extract_samples(base)
            if cur_samples and base_samples:
                ks = _ks_statistic(cur_samples, base_samples)
                ks_threshold = dist_cfg.get("ks_threshold")
                if ks is not None and ks_threshold is not None and ks > ks_threshold:
                    distribution_drifts.append(
                        {
                            "metric": metric,
                            "method": "ks",
                            "statistic": ks,
                            "threshold": ks_threshold,
                            "sample_count_current": len(cur_samples),
                            "sample_count_baseline": len(base_samples),
                        }
                    )

    if fail:
        status = "FAIL"
    elif drift or distribution_drifts:
        status = "PASS_WITH_DRIFT"
    else:
        status = "PASS"

    drift_sorted = sorted(drift, key=lambda item: abs(item["delta"]), reverse=True)
    return status, drift_sorted, warnings, fail, invariant_violations, distribution_drifts
