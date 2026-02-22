"""Map status + fail_metrics to WARN / FAIL / CRITICAL."""

def severity_for_status(status: str, fail_metrics: list | None = None, critical_metrics: set | None = None) -> str:
    if status == "FAIL":
        fail_metrics = fail_metrics or []
        critical_metrics = critical_metrics or set()
        if any(m in critical_metrics for m in fail_metrics):
            return "CRITICAL"
        return "FAIL"
    if status == "PASS_WITH_DRIFT":
        return "WARN"
    return "INFO"
