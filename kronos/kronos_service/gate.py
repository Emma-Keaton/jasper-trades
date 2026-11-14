"""Weight-aware admission control for forecast routes.

Wraps `RateLimiter` with standard rate-limit response headers so a rejected
caller can back off correctly, and converts the limiter's decision into the
HTTP layer's vocabulary.
"""

from __future__ import annotations

from fastapi import HTTPException, Response

from .limits import ApiKeyAuthoriser, LimitDecision, RateLimiter, default_policy


class ForecastGate:
    """Authenticate, then rate-limit, one container's forecast traffic."""

    def __init__(
        self,
        authoriser: ApiKeyAuthoriser | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.authoriser = authoriser or ApiKeyAuthoriser()
        self.limiter = limiter or RateLimiter(default_policy())

    def admit(
        self,
        x_api_key: str | None,
        weight: float,
        *,
        unit_weight: float | None = None,
    ) -> LimitDecision:
        """Authenticate and charge one request, or raise."""
        if not self.authoriser.configured:
            raise HTTPException(
                status_code=403,
                detail="KRONOS_API_KEY is not configured on the server; refusing to serve",
            )
        if not self.authoriser.verify(x_api_key):
            raise HTTPException(
                status_code=401, detail="invalid or missing X-API-Key"
            )
        decision = self.limiter.check(
            self.authoriser.expected,
            weight,
            unit_weight=unit_weight if unit_weight is not None else weight,
        )
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limited",
                    "weight": weight,
                    "retry_after_seconds": decision.retry_after,
                    "limit": decision.limit,
                },
                headers={
                    "retry-after": str(max(1, int(decision.retry_after + 0.999))),
                    "x-ratelimit-limit": str(decision.limit),
                    "x-ratelimit-remaining": "0",
                    "x-ratelimit-reset": str(int(decision.reset)),
                },
            )
        return decision

    @staticmethod
    def apply_headers(response: Response, decision: LimitDecision) -> Response:
        response.headers["x-ratelimit-limit"] = str(decision.limit)
        response.headers["x-ratelimit-remaining"] = str(int(decision.remaining))
        response.headers["x-ratelimit-reset"] = str(int(decision.reset))
        return response