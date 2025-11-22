import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import RateLimitExceededError
from app.core.rate_limiter import RateLimitConfig, SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API rate limiting.
    Uses a simple in-memory store for rate limiting with sliding window.
    """

    def __init__(
        self,
        app,
        rate_limit_per_minute: int = 60,
        api_key_header: str = "X-API-Key",
        api_keys: Optional[Dict[str, int]] = None,
        exclude_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.window_size = 60  # seconds
        # Per-identifier limiter instances using shared core implementation
        self._limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self.api_key_header = api_key_header
        self.api_keys = api_keys or {}  # Dict of {api_key: custom_rate_limit}
        self.exclude_paths = exclude_paths or []

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Determine client identifier (IP or API key)
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get(self.api_key_header)

        # Use API key as identifier if provided and valid, otherwise use IP
        identifier = api_key if api_key and api_key in self.api_keys else client_ip

        # Determine rate limit for this identifier
        rate_limit = self.api_keys.get(api_key, self.rate_limit_per_minute) if api_key else self.rate_limit_per_minute

        # Apply rate limiting using shared core sliding window limiter
        limiter = self._get_limiter(identifier, rate_limit)
        current_time = time.time()
        retry_after: Optional[float] = None
        try:
            await limiter.acquire(1)
            # If acquire succeeds, estimate current count for headers
            # Count timestamps in window for header math
            now = current_time
            window_start = now - self.window_size
            # Access internal state safely; this is a simple in-memory limiter
            request_count = len([t for t in limiter.request_times if t > window_start])
            is_allowed = True
        except RateLimitExceededError as e:
            is_allowed = False
            request_count = limiter.config.requests_per_hour
            retry_after = e.retry_after or self.window_size

        # Set rate limit headers
        headers = {
            "X-RateLimit-Limit": str(rate_limit),
            "X-RateLimit-Remaining": str(max(0, rate_limit - request_count)),
            "X-RateLimit-Reset": str(int(current_time + retry_after)) if retry_after else "0",
        }

        # If rate limit exceeded, return 429 with headers
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {identifier} on {request.url.path}")
            from fastapi.responses import JSONResponse

            response = JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded. Please try again later."}
                },
            )
            # Add rate limit headers to response
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            return response

        # Rate limit not exceeded, proceed with request
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response

    def _get_limiter(self, identifier: str, per_minute_limit: int) -> SlidingWindowRateLimiter:
        """Get or create a sliding window limiter for the identifier with a 60s window."""
        limiter = self._limiters.get(identifier)
        desired_limit = per_minute_limit  # treated as limit per 60s window
        if (
            limiter is None
            or limiter.config.requests_per_hour != desired_limit
            or limiter.config.window_seconds != self.window_size
        ):
            cfg = RateLimitConfig(
                requests_per_hour=desired_limit,  # interpreted as requests per window
                name=f"inbound:{identifier}",
                window_seconds=self.window_size,
            )
            limiter = SlidingWindowRateLimiter(cfg)
            self._limiters[identifier] = limiter
        return limiter
