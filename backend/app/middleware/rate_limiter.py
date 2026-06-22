"""
Rate Limiting Middleware for Production Security
Limits requests per minute per IP/device to prevent abuse
"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent API abuse.
    
    Configuration:
    - requests_per_minute: Max requests allowed per minute
    - burst: Allow temporary burst above limit
    - enabled: Toggle on/off
    
    Tracks requests by IP address or X-Device-ID header.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 100,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.enabled = enabled
        
        # Track request timestamps per client
        # Key: client_id, Value: list of timestamps
        self.request_history: dict[str, list[float]] = defaultdict(list)
        
        # Store limits for specific endpoints (stricter limits)
        self.strict_endpoints = {
            "/api/v1/withdrawal": {"requests_per_minute": 10, "burst": 20},
            "/api/v1/trading/execute": {"requests_per_minute": 30, "burst": 50},
            "/telegram/webhook": {"requests_per_minute": 120, "burst": 200},
        }

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Prefer device ID if available
        device_id = request.headers.get("X-Device-ID")
        if device_id:
            return f"device:{device_id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _is_rate_limited(self, client_id: str, endpoint: str) -> bool:
        """
        Check if client is rate limited.
        
        Uses sliding window algorithm:
        1. Remove timestamps older than 60 seconds
        2. Count remaining requests
        3. Compare against limit
        """
        current_time = time.time()
        window_start = current_time - 60.0  # 1-minute window
        
        # Get endpoint-specific limits or use defaults
        limits = self.strict_endpoints.get(endpoint, {
            "requests_per_minute": self.requests_per_minute,
            "burst": self.burst
        })
        
        max_requests = limits["requests_per_minute"]
        burst_limit = limits["burst"]
        
        # Clean old timestamps
        self.request_history[client_id] = [
            ts for ts in self.request_history[client_id]
            if ts > window_start
        ]
        
        # Check if over limit
        request_count = len(self.request_history[client_id])
        
        # Allow burst (2x limit for first window)
        effective_limit = max_requests * 2 if request_count < burst_limit else max_requests
        
        if request_count >= effective_limit:
            logger.warning(
                f"Rate limit exceeded",
                client_id=client_id[:20] + "***",
                endpoint=endpoint,
                request_count=request_count,
                limit=effective_limit,
            )
            return True
        
        # Record this request
        self.request_history[client_id].append(current_time)
        return False

    async def dispatch(self, request: Request, call_next):
        """Process each request through rate limiting."""
        # Skip rate limiting if disabled
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for health checks and static files
        path = request.url.path
        if path in ["/health", "/api/v1/health", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if self._is_rate_limited(client_id, path):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again in 60 seconds.",
                    "retry_after": 60,
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        # Calculate remaining (approximate)
        remaining = max(0, self.requests_per_minute - len(self.request_history.get(client_id, [])))
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


def create_rate_limit_middleware(
    requests_per_minute: int = 60,
    burst: int = 100,
    enabled: bool = True,
):
    """Factory function to create rate limit middleware."""
    return RateLimitMiddleware(
        requests_per_minute=requests_per_minute,
        burst=burst,
        enabled=enabled,
    )