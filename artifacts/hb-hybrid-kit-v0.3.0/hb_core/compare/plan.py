class ComparePlan:
    def __init__(
        self,
        metrics,
        metric_index,
        config_by_name,
        drift_thresholds,
        drift_percents,
        min_effects,
        fail_thresholds,
        invariant_min,
        invariant_max,
        invariant_eq,
        critical_flags,
    ):
        self.metrics = metrics
        self.metric_index = metric_index
        self.config_by_name = config_by_name
        self.drift_thresholds = drift_thresholds
        self.drift_percents = drift_percents
        self.min_effects = min_effects
        self.fail_thresholds = fail_thresholds
        self.invariant_min = invariant_min
        self.invariant_max = invariant_max
        self.invariant_eq = invariant_eq
        self.critical_flags = critical_flags

    @classmethod
    def compile(cls, metric_registry):
        metrics = sorted(metric_registry.get("metrics", {}).keys())
        metric_index = {name: idx for idx, name in enumerate(metrics)}
        config_by_name = metric_registry.get("metrics", {})
        drift_thresholds = []
        drift_percents = []
        min_effects = []
        fail_thresholds = []
        invariant_min = []
        invariant_max = []
        invariant_eq = []
        critical_flags = []
        for name in metrics:
            config = config_by_name.get(name, {})
            drift_thresholds.append(config.get("drift_threshold"))
            drift_percents.append(config.get("drift_percent"))
            min_effects.append(config.get("min_effect"))
            fail_thresholds.append(config.get("fail_threshold"))
            invariant_min.append(config.get("invariant_min"))
            invariant_max.append(config.get("invariant_max"))
            invariant_eq.append(config.get("invariant_eq"))
            critical_flags.append(bool(config.get("critical")))
        return cls(
            metrics,
            metric_index,
            config_by_name,
            drift_thresholds,
            drift_percents,
            min_effects,
            fail_thresholds,
            invariant_min,
            invariant_max,
            invariant_eq,
            critical_flags,
        )

    def index_metrics(self, metrics_map):
        values = [None] * len(self.metrics)
        for name, payload in metrics_map.items():
            idx = self.metric_index.get(name)
            if idx is None:
                continue
            values[idx] = payload
        return values
