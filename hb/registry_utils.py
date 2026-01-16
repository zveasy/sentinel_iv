import re


def normalize_alias(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def build_alias_index(metric_registry):
    index = {}
    for metric, config in metric_registry.get("metrics", {}).items():
        aliases = config.get("aliases", [])
        aliases = aliases + [metric]
        for alias in aliases:
            index[normalize_alias(alias)] = metric
    return index
