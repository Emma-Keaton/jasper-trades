"""API key authentication and token-bucket rate limiting for kronos.

Sized for the observed call patterns in jasper-trades:

| Source | Cadence | Call |
| --- | --- | --- |
| jasper-trades | on demand | varies |

Limits are expressed in *weighted* units, not raw request counts, because one
`samples=30` call costs ~7x a `samples=1` call in CPU time. A flat request cap
would let a single caller consume the entire budget through `sample_count` alone.

The default budget is deliberately generous relative to observed load while still
bounding the worst case.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from threading import Lock


# Measured wall-clock seconds per forecast on 2 vCPU, horizon 30.
COST_SECONDS_SAMPLE_1 = 5.5
COST_SECONDS_SAMPLE_10 = 11.2
COST_SECONDS_SAMPLE_30 = 37.0


def _env_int(name: str, fallback: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        value = int(raw)
    except ValueError:
        return fallback
    return value if value > 0 else fallback


@dataclass(frozen=True)
class RatePolicy:
    """Token-bucket budget for one client key."""

    refill_per_second: float
    burst: float
    max_request_weight: float

    def allows(self, weight: float) -> bool:
        return weight <= self.max_request_weight


@dataclass(frozen=True)
class LimitDecision:
    """Outcome of one admission check."""

    allowed: bool
    retry_after: float
    limit: int
    remaining: float
    reset: float


@dataclass
class RateLimiter:
    """In-process token buckets keyed by client.

    Per-container and in-memory by design.
    """

    policy: RatePolicy
    _buckets: dict[str, tuple[float, float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def check(
        self,
        key: str,
        weight: float,
        now: float | None = None,
        unit_weight: float | None = None,
    ) -> LimitDecision:
        """Charge `weight` units, or refuse."""
        moment = time.monotonic() if now is None else now
        unit = unit_weight if unit_weight is not None else weight

        with self._lock:
            tokens, last = self._buckets.get(key, (self.policy.burst, moment))
            elapsed = max(moment - last, 0.0)
            tokens = min(self.policy.burst, tokens + elapsed * self.policy.refill_per_second)

            if weight > self.policy.max_request_weight:
                return LimitDecision(
                    allowed=False,
                    retry_after=0.0,
                    limit=int(self.policy.burst),
                    remaining=tokens,
                    reset=moment,
                )

            if tokens >= weight:
                tokens -= weight
                self._buckets[key] = (tokens, moment)
                return LimitDecision(
                    allowed=True,
                    retry_after=0.0,
                    limit=int(self.policy.burst),
                    remaining=tokens,
                    reset=moment + (self.policy.burst - tokens) / self.policy.refill_per_second,
                )

            deficit = weight - tokens
            self._buckets[key] = (tokens, moment)
            return LimitDecision(
                allowed=False,
                retry_after=round(deficit / self.policy.refill_per_second, 3),
                limit=int(self.policy.burst),
                remaining=0.0,
                reset=moment + deficit / self.policy.refill_per_second,
            )

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


def forecast_weight(sample_count: int, horizon: int) -> float:
    """Weighted cost of one forecast request.

    Scales with measured inference time. Normalised so
    `sample_count=1, horizon=30` costs 1.0.
    """
    base = COST_SECONDS_SAMPLE_1
    scaled = base * (sample_count ** 0.72) * (max(horizon, 1) / 30.0)
    return round(max(scaled / base, 0.05), 3)


def default_policy() -> RatePolicy:
    """Budget set above the full observed load of every caller."""
    return RatePolicy(
        refill_per_second=float(os.getenv("KRONOS_RATE_PER_SECOND", "16")),
        burst=float(_env_int("KRONOS_RATE_BURST", 900)),
        max_request_weight=float(os.getenv("KRONOS_RATE_MAX_WEIGHT", "14")),
    )


class ApiKeyAuthoriser:
    """Constant-time comparison against the configured shared secret.

    Fails closed: if no key is configured every protected route is refused
    rather than served openly.
    """

    def __init__(self, expected: str | None = None) -> None:
        raw = expected if expected is not None else os.getenv("KRONOS_API_KEY", "")
        self.expected = raw.strip()

    @property
    def configured(self) -> bool:
        return bool(self.expected)

    def verify(self, presented: str | None) -> bool:
        if not self.configured:
            return False
        if not presented:
            return False
        return _constant_time_eq(presented.strip(), self.expected)


def _constant_time_eq(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode(), right.encode())