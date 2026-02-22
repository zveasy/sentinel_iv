from abc import ABC, abstractmethod
from typing import Any


class AlertSink(ABC):
    @abstractmethod
    def emit(self, event: dict[str, Any]) -> None:
        """Emit one alert event. event: ts, severity, status, run_id, primary_issue, report_path, drift_metrics[]."""
        pass
