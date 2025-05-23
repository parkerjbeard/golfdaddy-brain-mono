"""
Rate limiting implementation for external API calls.

Provides token bucket and sliding window rate limiting to prevent
exceeding API quotas and maintain service reliability.
"""

import asyncio
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior."""
    requests_per_hour: int
    burst_limit: Optional[int] = None  # Allow short bursts
    name: str = "default"


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, service_name: str, reset_time: float):
        self.service_name = service_name
        self.reset_time = reset_time
        self.retry_after = max(0, reset_time - time.time())
        super().__init__(
            f"Rate limit exceeded for '{service_name}'. "
            f"Retry after {self.retry_after:.1f} seconds."
        )


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter implementation.
    
    Allows for burst requests up to bucket capacity while maintaining
    an average rate over time.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.capacity = config.burst_limit or max(10, config.requests_per_hour // 60)
        self.tokens = self.capacity
        self.last_refill = time.time()
        self.refill_rate = config.requests_per_hour / 3600  # tokens per second
        self._lock = asyncio.Lock()
        
        logger.info(f"Initialized rate limiter '{config.name}' with "
                   f"{config.requests_per_hour} requests/hour, "
                   f"burst capacity: {self.capacity}")
    
    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Raises:
            RateLimitExceededError: When insufficient tokens available
        """
        async with self._lock:
            self._refill_bucket()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Acquired {tokens} tokens for '{self.config.name}', "
                           f"remaining: {self.tokens}")
            else:
                # Calculate when enough tokens will be available
                needed_tokens = tokens - self.tokens
                wait_time = needed_tokens / self.refill_rate
                reset_time = time.time() + wait_time
                
                logger.warning(f"Rate limit exceeded for '{self.config.name}', "
                             f"need {needed_tokens} more tokens")
                raise RateLimitExceededError(self.config.name, reset_time)
    
    def _refill_bucket(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    @property
    def status(self) -> Dict[str, any]:
        """Get current rate limiter status."""
        self._refill_bucket()
        return {
            "name": self.config.name,
            "available_tokens": self.tokens,
            "capacity": self.capacity,
            "refill_rate": self.refill_rate,
            "requests_per_hour": self.config.requests_per_hour
        }


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter implementation.
    
    Tracks request timestamps in a sliding window to enforce
    strict rate limits over time periods.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.window_size = 3600  # 1 hour in seconds
        self.request_times: list = []
        self._lock = asyncio.Lock()
        
        logger.info(f"Initialized sliding window rate limiter '{config.name}' with "
                   f"{config.requests_per_hour} requests/hour")
    
    async def acquire(self, requests: int = 1) -> None:
        """
        Acquire permission for requests.
        
        Args:
            requests: Number of requests to acquire
            
        Raises:
            RateLimitExceededError: When rate limit would be exceeded
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # Remove expired requests
            self.request_times = [t for t in self.request_times if t > window_start]
            
            # Check if adding requests would exceed limit
            if len(self.request_times) + requests > self.config.requests_per_hour:
                # Calculate when oldest request will expire
                if self.request_times:
                    oldest_request = min(self.request_times)
                    reset_time = oldest_request + self.window_size
                else:
                    reset_time = now + self.window_size
                
                logger.warning(f"Rate limit exceeded for '{self.config.name}', "
                             f"current requests: {len(self.request_times)}")
                raise RateLimitExceededError(self.config.name, reset_time)
            
            # Add request timestamps
            for _ in range(requests):
                self.request_times.append(now)
            
            logger.debug(f"Acquired {requests} requests for '{self.config.name}', "
                        f"total in window: {len(self.request_times)}")
    
    @property
    def status(self) -> Dict[str, any]:
        """Get current rate limiter status."""
        now = time.time()
        window_start = now - self.window_size
        current_requests = len([t for t in self.request_times if t > window_start])
        
        return {
            "name": self.config.name,
            "current_requests": current_requests,
            "limit": self.config.requests_per_hour,
            "window_size": self.window_size,
            "remaining": max(0, self.config.requests_per_hour - current_requests)
        }


class RateLimiterManager:
    """
    Manages multiple rate limiters for different services.
    """
    
    def __init__(self):
        self._limiters: Dict[str, TokenBucketRateLimiter] = {}
    
    def create_limiter(self, name: str, config: RateLimitConfig, 
                      limiter_type: str = "token_bucket") -> TokenBucketRateLimiter:
        """Create and register a new rate limiter."""
        config.name = name
        
        if limiter_type == "token_bucket":
            limiter = TokenBucketRateLimiter(config)
        elif limiter_type == "sliding_window":
            limiter = SlidingWindowRateLimiter(config)
        else:
            raise ValueError(f"Unknown limiter type: {limiter_type}")
        
        self._limiters[name] = limiter
        return limiter
    
    def get_limiter(self, name: str) -> Optional[TokenBucketRateLimiter]:
        """Get rate limiter by name."""
        return self._limiters.get(name)
    
    def get_status(self) -> Dict[str, Dict[str, any]]:
        """Get status of all rate limiters."""
        return {name: limiter.status for name, limiter in self._limiters.items()}
    
    @asynccontextmanager
    async def acquire(self, service_name: str, tokens: int = 1):
        """Context manager for acquiring rate limit tokens."""
        limiter = self.get_limiter(service_name)
        if limiter:
            await limiter.acquire(tokens)
        
        try:
            yield
        finally:
            # Nothing to cleanup for token bucket
            pass


# Global rate limiter manager instance
rate_limiter_manager = RateLimiterManager()


def create_github_rate_limiter() -> TokenBucketRateLimiter:
    """Create rate limiter for GitHub API calls."""
    from app.config.settings import settings
    
    config = RateLimitConfig(
        requests_per_hour=getattr(settings, 'GITHUB_API_RATE_LIMIT', 5000),
        burst_limit=50,  # Allow bursts for batch operations
        name="github_api"
    )
    return rate_limiter_manager.create_limiter("github_api", config)


def create_openai_rate_limiter() -> TokenBucketRateLimiter:
    """Create rate limiter for OpenAI API calls."""
    from app.config.settings import settings
    
    config = RateLimitConfig(
        requests_per_hour=getattr(settings, 'OPENAI_API_RATE_LIMIT', 3500),
        burst_limit=10,  # Conservative burst for AI calls
        name="openai_api"
    )
    return rate_limiter_manager.create_limiter("openai_api", config)


# Decorator for automatic rate limiting
def rate_limited(service_name: str, tokens: int = 1):
    """
    Decorator for applying rate limiting to functions.
    
    Args:
        service_name: Name of the rate limiter to use
        tokens: Number of tokens to acquire
        
    Example:
        @rate_limited("github_api", tokens=1)
        async def call_github_api():
            # API call implementation
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            limiter = rate_limiter_manager.get_limiter(service_name)
            if limiter:
                await limiter.acquire(tokens)
            return await func(*args, **kwargs)
        return wrapper
    return decorator