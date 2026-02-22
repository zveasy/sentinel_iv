"""
Property-based tests for compare engine: same inputs -> same outputs; alias normalization.
Requires: pip install hypothesis (or skip).
"""
import pytest

from hb.config import _normalize_metric_registry
from hb.engine import compare_metrics
from hb.registry_utils import normalize_alias

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False


def _minimal_registry(metric_names):
    alias_index = {}
    metrics = {}
    for name in metric_names:
        alias_index[name] = name
        alias_index[name.lower()] = name
        alias_index[normalize_alias(name)] = name
        metrics[name] = {"unit": None, "drift_threshold": 1.0}
    return _normalize_metric_registry({"alias_index": alias_index, "metrics": metrics})


if HAS_HYPOTHESIS:
    @given(
        current=st.dictionaries(
            keys=st.text(min_size=1, max_size=15, alphabet="T2P2N2ABC").filter(lambda s: normalize_alias(s)),
            values=st.builds(
                lambda v: {"value": v},
                st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
            ),
            min_size=1,
            max_size=6,
        ),
        baseline=st.dictionaries(
            keys=st.text(min_size=1, max_size=15, alphabet="T2P2N2ABC").filter(lambda s: normalize_alias(s)),
            values=st.builds(
                lambda v: {"value": v},
                st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
            ),
            min_size=1,
            max_size=6,
        ),
    )
    @settings(max_examples=60, deadline=2000)
    def test_compare_metrics_deterministic_same_input_same_output(current, baseline):
        """Same (current, baseline, registry) must yield same status and drift count."""
        def to_metrics(d):
            return {k: {"value": v["value"], "unit": None, "tags": None} for k, v in d.items()}
        c = to_metrics(current)
        b = to_metrics(baseline)
        all_names = sorted(set(c.keys()) | set(b.keys()))
        registry = _minimal_registry(all_names)
        c = {k: v for k, v in c.items() if k in registry["metrics"]}
        b = {k: v for k, v in b.items() if k in registry["metrics"]}
        if not c:
            return
        status1, drift1, _, _, _, _, _ = compare_metrics(c, b, registry, distribution_enabled=False, plan=None)
        status2, drift2, _, _, _, _, _ = compare_metrics(c, b, registry, distribution_enabled=False, plan=None)
        assert status1 == status2
        assert len(drift1) == len(drift2)

    @given(
        name=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_"),
    )
    def test_normalize_alias_roundtrip_consistency(name):
        """normalize_alias is deterministic and idempotent for ASCII alphanumeric."""
        n = normalize_alias(name)
        assert n == normalize_alias(n)
        assert n == normalize_alias(name.lower())
        assert n.isalnum() or n == ""
else:
    @pytest.mark.skip(reason="hypothesis not installed")
    def test_compare_metrics_deterministic_same_input_same_output(current=None, baseline=None):
        pass

    @pytest.mark.skip(reason="hypothesis not installed")
    def test_normalize_alias_roundtrip_consistency(name=""):
        pass
