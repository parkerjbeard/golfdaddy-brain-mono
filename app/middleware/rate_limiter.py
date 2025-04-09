import time
from typing import Dict, Tuple, Callable, Optional
from fastapi import Request, Response, HTTPException
import logging
from starlette.middleware.base import BaseHTTPMiddleware

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
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.window_size = 60  # 1 minute in seconds
        self.request_store: Dict[str, list] = {}  # Store of {identifier: [timestamps]}
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
        
        # Apply rate limiting
        current_time = time.time()
        is_allowed, request_count, retry_after = self._check_rate_limit(identifier, current_time, rate_limit)
        
        # Set rate limit headers
        headers = {
            "X-RateLimit-Limit": str(rate_limit),
            "X-RateLimit-Remaining": str(max(0, rate_limit - request_count)),
            "X-RateLimit-Reset": str(int(current_time + retry_after)) if retry_after else "0"
        }
        
        # If rate limit exceeded, return 429 with headers
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {identifier} on {request.url.path}")
            error_response = Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=429,
                headers=headers
            )
            return error_response
            
        # Rate limit not exceeded, proceed with request
        response = await call_next(request)
        
        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
            
        return response
    
    def _check_rate_limit(
        self, identifier: str, current_time: float, rate_limit: int
    ) -> Tuple[bool, int, Optional[float]]:
        """
        Check if the request is within rate limits.
        
        Args:
            identifier: Client identifier (IP or API key)
            current_time: Current timestamp
            rate_limit: Maximum requests allowed per minute
            
        Returns:
            (is_allowed, current_count, retry_after_seconds)
        """
        # Initialize empty list if identifier not in store
        if identifier not in self.request_store:
            self.request_store[identifier] = []
            
        # Remove timestamps older than the window
        self.request_store[identifier] = [
            ts for ts in self.request_store[identifier] 
            if current_time - ts < self.window_size
        ]
        
        # Count requests in the current window
        request_count = len(self.request_store[identifier])
        
        # Check if adding this request exceeds the limit
        if request_count >= rate_limit:
            # Calculate when the oldest request will expire
            oldest_timestamp = min(self.request_store[identifier]) if self.request_store[identifier] else current_time
            retry_after = max(0, self.window_size - (current_time - oldest_timestamp))
            return False, request_count, retry_after
            
        # Add current request timestamp to the store
        self.request_store[identifier].append(current_time)
        
        return True, request_count + 1, None 