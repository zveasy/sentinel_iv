import yaml


def _mask_value(value, strategy):
    if value is None:
        return None
    if strategy == "redact":
        return "[REDACTED]"
    if strategy == "hash":
        import hashlib

        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    if strategy == "truncate":
        return str(value)[:4] + "..."
    return value


def apply_redaction(policy_path, run_meta, profile=None):
    """
    Apply redaction rules to run_meta. If profile is set, use policy["profiles"][profile]["redact"];
    otherwise use policy["redact"]. Policy YAML may have: redact: {...} or profiles: { name: { redact: {...} } }.
    """
    with open(policy_path, "r") as f:
        policy = yaml.safe_load(f) or {}
    if profile and isinstance(policy.get("profiles"), dict) and profile in policy["profiles"]:
        rules = policy["profiles"][profile].get("redact", {})
    else:
        rules = policy.get("redact", {})
    for field, strategy in rules.items():
        if "." in field:
            parts = field.split(".")
            target = run_meta
            for key in parts[:-1]:
                target = target.get(key, {})
            if parts[-1] in target:
                target[parts[-1]] = _mask_value(target.get(parts[-1]), strategy)
        else:
            if field in run_meta:
                run_meta[field] = _mask_value(run_meta.get(field), strategy)
    return run_meta
