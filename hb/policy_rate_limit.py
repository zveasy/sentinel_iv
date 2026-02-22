"""
Rate-limited policy updates for staged rollout and rollback (roadmap 6.2.2).
Use when applying baseline or config changes to avoid thundering herd and allow rollback.
"""
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PolicyRateLimitConfig:
    """Config for policy update rate limiting."""
    max_updates_per_minute: float = 10.0
    min_interval_sec: float = 6.0  # minimum seconds between updates


class PolicyRateLimiter:
    """
    Token-bucket style: allow at most max_updates_per_minute, with min_interval_sec between updates.
    Call allow() before applying a policy update; if False, defer or queue.
    """
    def __init__(self, config: Optional[PolicyRateLimitConfig] = None):
        self.config = config or PolicyRateLimitConfig()
        self._last_update_time: float = 0.0
        self._tokens: float = float(self.config.max_updates_per_minute)  # refill over time

    def allow(self) -> bool:
        """
        Returns True if an update is allowed now. When True, consumes one token.
        Call this before applying a policy/baseline update.
        """
        now = time.monotonic()
        elapsed_min = (now - self._last_update_time) / 60.0
        # Refill tokens proportionally to elapsed time
        self._tokens = min(
            self.config.max_updates_per_minute,
            self._tokens + elapsed_min * self.config.max_updates_per_minute,
        )
        if self._tokens < 1.0:
            return False
        if self._last_update_time > 0 and (now - self._last_update_time) < self.config.min_interval_sec:
            return False
        self._tokens -= 1.0
        self._last_update_time = now
        return True

    def time_until_next_sec(self) -> float:
        """Seconds until the next update would be allowed (0 if allowed now)."""
        now = time.monotonic()
        if self._tokens >= 1.0 and (self._last_update_time == 0 or (now - self._last_update_time) >= self.config.min_interval_sec):
            return 0.0
        if self._last_update_time > 0:
            remaining = self.config.min_interval_sec - (now - self._last_update_time)
            if remaining > 0:
                return remaining
        # Wait for one token refill
        need = 1.0 - self._tokens
        if need <= 0:
            return 0.0
        return (need / self.config.max_updates_per_minute) * 60.0
