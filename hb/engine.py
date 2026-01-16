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
        normalized[canonical] = {"value": value, "unit": unit}
    return normalized, sorted(warnings)


def compare_metrics(current, baseline, metric_registry):
    drift = []
    warnings = []
    fail = []
    all_metrics = sorted(set(current.keys()) | set(baseline.keys()))
    for metric in all_metrics:
        config = metric_registry["metrics"].get(metric, {})
        cur = current.get(metric)
        base = baseline.get(metric)
        if cur is None or cur.get("value") is None:
            warnings.append(f"missing current metric: {metric}")
            continue
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

    if fail:
        status = "FAIL"
    elif drift:
        status = "PASS_WITH_DRIFT"
    else:
        status = "PASS"

    drift_sorted = sorted(drift, key=lambda item: abs(item["delta"]), reverse=True)
    return status, drift_sorted, warnings, fail
