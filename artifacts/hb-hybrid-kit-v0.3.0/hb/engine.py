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


def _percentile(sorted_values, pct):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return float(sorted_values[low] * (1 - weight) + sorted_values[high] * weight)


def _stats_from_samples(samples, fallback_value):
    if samples:
        values = sorted(samples)
        count = len(values)
        mean = sum(values) / count
        median = _percentile(values, 0.5)
        p95 = _percentile(values, 0.95)
        variance = sum((value - mean) ** 2 for value in values) / count
        std = variance ** 0.5
        return {
            "mean": mean,
            "median": median,
            "p95": p95,
            "std": std,
            "count": count,
        }
    if fallback_value is None:
        return {"mean": None, "median": None, "p95": None, "std": None, "count": 0}
    return {
        "mean": fallback_value,
        "median": fallback_value,
        "p95": fallback_value,
        "std": 0.0,
        "count": 1,
    }


def _confidence_from_count(count):
    if count >= 200:
        return "high"
    if count >= 50:
        return "medium"
    if count > 0:
        return "low"
    return None


def _pearson_corr(values, scores):
    if not values or not scores or len(values) != len(scores):
        return None
    n = len(values)
    if n < 2:
        return None
    mean_x = sum(values) / n
    mean_y = sum(scores) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(values, scores))
    den_x = sum((x - mean_x) ** 2 for x in values) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in scores) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _exceeds_threshold(delta, baseline_mean, drift_threshold, drift_percent, zscore):
    if drift_threshold is not None:
        return abs(delta) >= drift_threshold
    if drift_percent is not None and baseline_mean not in (None, 0):
        return abs(delta / baseline_mean * 100.0) >= drift_percent
    if zscore is not None:
        return abs(zscore) >= 3.0
    return False


def _onset_and_evidence(samples, baseline_stats, config):
    if not samples:
        return None, None, None
    baseline_mean = baseline_stats.get("mean")
    baseline_std = baseline_stats.get("std")
    drift_threshold = config.get("drift_threshold")
    drift_percent = config.get("drift_percent")
    persistence = int(config.get("drift_persistence", 5))

    drift_scores = []
    exceeds = []
    for value in samples:
        delta = value - baseline_mean if baseline_mean is not None else None
        zscore = None
        if baseline_std and baseline_std > 0 and delta is not None:
            zscore = delta / baseline_std
        drift_score = zscore if zscore is not None else delta
        drift_scores.append(drift_score)
        exceeds.append(_exceeds_threshold(delta or 0, baseline_mean, drift_threshold, drift_percent, zscore))

    first_exceed = None
    for idx, flag in enumerate(exceeds):
        if flag:
            first_exceed = idx
            break

    sustained = None
    streak = 0
    for idx, flag in enumerate(exceeds):
        if flag:
            streak += 1
            if streak >= persistence:
                sustained = idx - persistence + 1
                break
        else:
            streak = 0

    onset = {
        "first_exceed_index": first_exceed,
        "sustained_index": sustained,
        "persistence": persistence,
    }

    evidence = []
    onset_idx = sustained if sustained is not None else first_exceed
    if onset_idx is not None:
        start = max(0, onset_idx - 3)
        end = min(len(samples), onset_idx + 4)
    else:
        start = 0
        end = min(len(samples), 7)
    for idx in range(start, end):
        evidence.append(
            {
                "index": idx,
                "value": samples[idx],
                "drift_score": drift_scores[idx],
            }
        )
    return onset, evidence, drift_scores


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
    attribution = []
    all_metrics = sorted(set(current.keys()) | set(baseline.keys()))
    if not all_metrics:
        warnings.append("no metrics evaluated")
        return "NO_METRICS", drift, warnings, fail, invariant_violations, distribution_drifts, attribution
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

        base_samples = _extract_samples(base)
        cur_samples = _extract_samples(cur)
        baseline_stats = _stats_from_samples(base_samples, base["value"])
        current_stats = _stats_from_samples(cur_samples, cur["value"])
        baseline_std = baseline_stats.get("std")
        zscore = None
        if baseline_std and baseline_std > 0:
            zscore = delta / baseline_std
        onset, evidence, drift_scores = _onset_and_evidence(cur_samples, baseline_stats, config)

        decision_basis = []
        if is_drift:
            if drift_threshold is not None:
                decision_basis.append("drift_threshold")
            if drift_percent is not None:
                decision_basis.append("drift_percent")
        if metric in fail:
            decision_basis.append("critical")

        driver_score = None
        if zscore is not None:
            driver_score = abs(zscore)
        elif percent is not None:
            driver_score = abs(percent)
        else:
            driver_score = abs(delta)

        raw_features = config.get("source_columns") or []
        if isinstance(raw_features, str):
            raw_features = [raw_features]
        raw_feature_correlations = []
        corr_method = "pearson"
        n_points_used = len(cur_samples) if cur_samples else 0
        min_abs_corr_display = 0.30
        correlation_note = None
        if cur_samples and drift_scores:
            corr = _pearson_corr(cur_samples, drift_scores)
            if corr is not None and abs(corr) >= min_abs_corr_display:
                for feature in raw_features or ["value"]:
                    raw_feature_correlations.append({"feature": feature, "corr": corr})
            else:
                correlation_note = "low attribution confidence"

        flagged = is_drift or metric in fail
        if drift_threshold is not None:
            warn_threshold = drift_threshold
        elif drift_percent is not None:
            warn_threshold = drift_percent
        else:
            warn_threshold = None
        score_type = "delta"
        if zscore is not None:
            score_type = "zscore"
        elif percent is not None:
            score_type = "percent"
        attribution.append(
            {
                "metric_name": metric,
                "direction": "up" if delta >= 0 else "down",
                "effect_size": {
                    "delta": delta,
                    "percent": percent,
                    "zscore": zscore,
                },
                "baseline_stats": {
                    "mean": baseline_stats.get("mean"),
                    "median": baseline_stats.get("median"),
                    "p95": baseline_stats.get("p95"),
                },
                "current_stats": {
                    "mean": current_stats.get("mean"),
                    "median": current_stats.get("median"),
                    "p95": current_stats.get("p95"),
                },
                "confidence": _confidence_from_count(
                    min(baseline_stats.get("count", 0), current_stats.get("count", 0))
                ),
                "onset": onset,
                "raw_features": raw_features,
                "raw_feature_correlations": raw_feature_correlations or None,
                "corr_method": corr_method,
                "n_points_used": n_points_used,
                "min_abs_corr_display": min_abs_corr_display,
                "correlation_note": correlation_note,
                "evidence": evidence,
                "decision_basis": decision_basis,
                "score": driver_score,
                "drift_score": driver_score,
                "warn_threshold": warn_threshold,
                "fail_threshold": config.get("fail_threshold"),
                "persistence_cycles": int(config.get("drift_persistence", 5)),
                "score_type": score_type,
                "drift_threshold": drift_threshold,
                "drift_percent": drift_percent,
                "flagged": flagged,
            }
        )

    if fail:
        status = "FAIL"
    elif drift or distribution_drifts:
        status = "PASS_WITH_DRIFT"
    else:
        status = "PASS"

    drift_sorted = sorted(drift, key=lambda item: abs(item["delta"]), reverse=True)
    attribution_map = {item["metric_name"]: item for item in attribution}
    for item in distribution_drifts:
        entry = attribution_map.get(item["metric"])
        if entry:
            entry["effect_size"]["ks"] = item.get("statistic")
            entry["decision_basis"].append("distribution_ks")
            if entry.get("score") is None and item.get("statistic") is not None:
                entry["score"] = abs(item["statistic"])
    for item in attribution:
        if item.get("score") is None:
            item["score"] = 0.0
    flagged_metrics = {item["metric"] for item in distribution_drifts}
    filtered = [
        item
        for item in attribution
        if item.get("flagged") or item.get("metric_name") in flagged_metrics
    ]
    top_drivers = sorted(filtered, key=lambda item: abs(item.get("score", 0.0)), reverse=True)
    return status, drift_sorted, warnings, fail, invariant_violations, distribution_drifts, top_drivers
