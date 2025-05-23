"""
Circuit Breaker pattern implementation for external service reliability.

Provides protection against cascading failures by monitoring external service health
and temporarily disabling calls when services are failing consistently.
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict, Union
from dataclasses import dataclass
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, calls blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5
    timeout: int = 60
    recovery_timeout: int = 30
    expected_exception: tuple = (Exception,)
    name: str = "default"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking calls."""
    
    def __init__(self, circuit_name: str, failure_count: int, timeout: int):
        self.circuit_name = circuit_name
        self.failure_count = failure_count
        self.timeout = timeout
        super().__init__(
            f"Circuit breaker '{circuit_name}' is OPEN. "
            f"Failed {failure_count} times. Retry after {timeout}s."
        )


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable failure thresholds and timeouts.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are blocked
    - HALF_OPEN: Testing if service has recovered
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"Initialized circuit breaker '{config.name}' with "
                   f"failure_threshold={config.failure_threshold}, "
                   f"timeout={config.timeout}s")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            Exception: Original function exceptions when circuit is closed
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker '{self.config.name}' moved to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        self.config.name, 
                        self.failure_count, 
                        self.config.timeout
                    )
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - update state
            await self._on_success()
            return result
            
        except self.config.expected_exception as e:
            # Expected failure - update state
            await self._on_failure()
            raise e
    
    async def _on_success(self):
        """Handle successful function execution."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= 3:  # Require multiple successes to close
                    self._reset()
                    logger.info(f"Circuit breaker '{self.config.name}' CLOSED after recovery")
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                if self.failure_count > 0:
                    self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed function execution."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery test - back to open
                self.state = CircuitState.OPEN
                self.success_count = 0
                logger.warning(f"Circuit breaker '{self.config.name}' failed recovery test, "
                             f"returning to OPEN state")
            elif (self.state == CircuitState.CLOSED and 
                  self.failure_count >= self.config.failure_threshold):
                # Too many failures - open circuit
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker '{self.config.name}' OPENED after "
                           f"{self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        return (time.time() - self.last_failure_time) >= self.config.timeout
    
    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "timeout": self.config.timeout,
                "recovery_timeout": self.config.recovery_timeout
            }
        }


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers for different services.
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def create_breaker(self, name: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Create and register a new circuit breaker."""
        config.name = name
        breaker = CircuitBreaker(config)
        self._breakers[name] = breaker
        return breaker
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {name: breaker.status for name, breaker in self._breakers.items()}
    
    def reset_breaker(self, name: str) -> bool:
        """Manually reset a circuit breaker."""
        breaker = self._breakers.get(name)
        if breaker:
            breaker._reset()
            logger.info(f"Manually reset circuit breaker '{name}'")
            return True
        return False


# Global circuit breaker manager instance
circuit_manager = CircuitBreakerManager()


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: int = 60,
    recovery_timeout: int = 30,
    expected_exception: tuple = (Exception,)
) -> Callable:
    """
    Decorator for applying circuit breaker pattern to functions.
    
    Args:
        name: Unique name for the circuit breaker
        failure_threshold: Number of failures before opening circuit
        timeout: Seconds to wait before attempting recovery
        recovery_timeout: Seconds to wait for recovery confirmation
        expected_exception: Exception types that trigger circuit breaker
        
    Example:
        @circuit_breaker("github_api", failure_threshold=3, timeout=30)
        async def call_github_api():
            # API call implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        # Create circuit breaker for this function
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=timeout,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=name
        )
        breaker = circuit_manager.create_breaker(name, config)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(breaker.call(func, *args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Convenience function for creating service-specific circuit breakers
def create_github_circuit_breaker() -> CircuitBreaker:
    """Create circuit breaker for GitHub API calls."""
    from app.config.settings import settings
    
    config = CircuitBreakerConfig(
        failure_threshold=getattr(settings, 'GITHUB_CIRCUIT_BREAKER_FAILURE_THRESHOLD', 5),
        timeout=getattr(settings, 'GITHUB_CIRCUIT_BREAKER_TIMEOUT', 60),
        expected_exception=(Exception,),  # Will be refined for specific GitHub exceptions
        name="github_api"
    )
    return circuit_manager.create_breaker("github_api", config)


def create_openai_circuit_breaker() -> CircuitBreaker:
    """Create circuit breaker for OpenAI API calls."""
    from app.config.settings import settings
    
    config = CircuitBreakerConfig(
        failure_threshold=getattr(settings, 'OPENAI_CIRCUIT_BREAKER_FAILURE_THRESHOLD', 3),
        timeout=getattr(settings, 'OPENAI_CIRCUIT_BREAKER_TIMEOUT', 30),
        expected_exception=(Exception,),  # Will be refined for specific OpenAI exceptions
        name="openai_api"
    )
    return circuit_manager.create_breaker("openai_api", config)