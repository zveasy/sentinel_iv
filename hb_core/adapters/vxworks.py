import csv
import json
import os
import re
import time
from collections import Counter

from hb_core.adapters.base import ArtifactAdapter
from hb_core.artifact import ARTIFACT_SCHEMA_VERSION, validate_artifact_dir


class VxWorksLogAdapter(ArtifactAdapter):
    name = "vxworks_logs"

    def export(self, log_path, out_dir, run_meta=None, baseline_log_path=None, profile_path=None):
        if not os.path.exists(log_path):
            raise ValueError(f"log_path not found: {log_path}")
        os.makedirs(out_dir, exist_ok=True)

        profile = None
        if profile_path and os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                profile = json.load(f)
        elif baseline_log_path:
            if not os.path.exists(baseline_log_path):
                raise ValueError(f"baseline_log_path not found: {baseline_log_path}")
            profile = _infer_profile(baseline_log_path)
            with open(os.path.join(out_dir, "parser_profile.json"), "w") as f:
                json.dump(profile, f, indent=2)

        if isinstance(run_meta, str):
            with open(run_meta, "r") as f:
                run_meta = json.load(f)
        run_meta = run_meta or {}
        run_meta.setdefault("schema_version", ARTIFACT_SCHEMA_VERSION)
        run_meta.setdefault("program", "vxworks")
        run_meta.setdefault("subsystem", "vxworks")
        run_meta.setdefault("test_name", "vxworks_log_analysis")
        run_meta.setdefault(
            "timestamps",
            {"start_utc": "", "end_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        )

        counts, template_stats = _parse_log(log_path, profile)

        with open(os.path.join(out_dir, "run_meta.json"), "w") as f:
            json.dump(run_meta, f, indent=2)

        with open(os.path.join(out_dir, "metrics.csv"), "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value", "unit", "tags"])
            for metric, value in counts.items():
                writer.writerow([metric, value, "", ""])
            for metric, value in template_stats.items():
                writer.writerow([metric, value, "", ""])

        if template_stats:
            with open(os.path.join(out_dir, "template_stats.json"), "w") as f:
                json.dump(template_stats, f, indent=2)

        validate_artifact_dir(out_dir)
        return out_dir


def _infer_profile(baseline_log_path):
    with open(baseline_log_path, "r", errors="replace") as f:
        lines = f.readlines()

    ts_patterns = {
        "iso": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        "hms": re.compile(r"^\d{2}:\d{2}:\d{2}"),
        "uptime": re.compile(r"^\[\d+(\.\d+)?\]"),
    }
    ts_counts = {name: 0 for name in ts_patterns}
    severity_tokens = Counter()
    module_prefix = Counter()
    templates = Counter()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        for name, pattern in ts_patterns.items():
            if pattern.search(line):
                ts_counts[name] += 1
        severity = _extract_severity(line)
        if severity:
            severity_tokens[severity] += 1
        prefix = _extract_prefix(line)
        if prefix:
            module_prefix[prefix] += 1
        templates[_templateize(line)] += 1

    dominant_ts = max(ts_counts, key=ts_counts.get) if any(ts_counts.values()) else "none"
    return {
        "timestamp_style": dominant_ts,
        "severity_tokens": [tok for tok, _ in severity_tokens.most_common(6)],
        "prefixes": [p for p, _ in module_prefix.most_common(6)],
        "templates": [t for t, _ in templates.most_common(50)],
    }


def _extract_severity(line):
    tokens = [
        ("ERROR", re.compile(r"\bERROR\b|\bERR\b|\bE\b", re.IGNORECASE)),
        ("WARN", re.compile(r"\bWARN(ING)?\b|\bWRN\b|\bW\b", re.IGNORECASE)),
        ("INFO", re.compile(r"\bINFO\b|\bINF\b|\bI\b", re.IGNORECASE)),
        ("DEBUG", re.compile(r"\bDEBUG\b|\bDBG\b|\bD\b", re.IGNORECASE)),
    ]
    for label, pattern in tokens:
        if pattern.search(line):
            return label
    return None


def _extract_prefix(line):
    match = re.match(r"^([A-Za-z0-9_/-]+):", line)
    if match:
        return match.group(1)
    return None


def _templateize(line):
    line = re.sub(r"0x[0-9a-fA-F]+", "<hex>", line)
    line = re.sub(r"\b\d+\b", "<int>", line)
    line = re.sub(r"\b\d+\.\d+\b", "<float>", line)
    line = re.sub(r"\b[a-zA-Z]+[0-9]+\b", "<id>", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def _parse_log(log_path, profile):
    counts = {
        "error_count": 0,
        "warn_count": 0,
        "reset_count": 0,
        "total_lines": 0,
    }
    reset_re = re.compile(r"\bRESET\b", re.IGNORECASE)
    templates = []
    with open(log_path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            counts["total_lines"] += 1
            severity = _extract_severity(line)
            if severity == "ERROR":
                counts["error_count"] += 1
            if severity == "WARN":
                counts["warn_count"] += 1
            if reset_re.search(line):
                counts["reset_count"] += 1
            templates.append(_templateize(line))

    template_stats = {}
    if profile and profile.get("templates"):
        known = set(profile.get("templates", []))
        matched = sum(1 for t in templates if t in known)
        new_templates = sorted({t for t in templates if t not in known})
        template_stats = {
            "template_match_rate": round((matched / counts["total_lines"]) * 100, 2)
            if counts["total_lines"]
            else 0.0,
            "new_template_count": len(new_templates),
            "known_template_count": len(known),
        }
        with open(os.path.join(os.path.dirname(log_path), "template_new.json"), "w") as f:
            json.dump(new_templates[:100], f, indent=2)
    return counts, template_stats
