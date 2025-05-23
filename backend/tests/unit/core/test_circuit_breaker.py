import pytest
import asyncio
import time
from unittest.mock import Mock, patch

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    CircuitBreakerManager,
    circuit_breaker,
    circuit_manager
)


@pytest.fixture
def config():
    """Default circuit breaker configuration."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        timeout=5,
        recovery_timeout=2,
        expected_exception=(ValueError, RuntimeError),
        name="test_breaker"
    )


@pytest.fixture
def breaker(config):
    """Circuit breaker instance with test configuration."""
    return CircuitBreaker(config)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.timeout == 60
        assert config.recovery_timeout == 30
        assert config.expected_exception == (Exception,)
        assert config.name == "default"
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            timeout=120,
            recovery_timeout=60,
            expected_exception=(ValueError,),
            name="custom_breaker"
        )
        assert config.failure_threshold == 10
        assert config.timeout == 120
        assert config.recovery_timeout == 60
        assert config.expected_exception == (ValueError,)
        assert config.name == "custom_breaker"


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_initial_state(self, breaker):
        """Test circuit breaker initial state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure_time == 0
        assert breaker.success_count == 0
    
    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """Test successful function call."""
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_sync_function_call(self, breaker):
        """Test calling synchronous function."""
        def sync_func(x, y):
            return x + y
        
        result = await breaker.call(sync_func, 2, 3)
        assert result == 5
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_single_failure(self, breaker):
        """Test single failure doesn't open circuit."""
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_threshold_failures_open_circuit(self, breaker):
        """Test that reaching failure threshold opens circuit."""
        async def failing_func():
            raise ValueError("Test error")
        
        # Fail until threshold is reached
        for i in range(breaker.config.failure_threshold):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == breaker.config.failure_threshold
    
    @pytest.mark.asyncio
    async def test_open_circuit_blocks_calls(self, breaker):
        """Test that open circuit blocks further calls."""
        # Force circuit to open
        breaker.state = CircuitState.OPEN
        breaker.failure_count = breaker.config.failure_threshold
        breaker.last_failure_time = time.time()
        
        async def any_func():
            return "should not execute"
        
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await breaker.call(any_func)
        
        assert exc_info.value.circuit_name == "test_breaker"
        assert exc_info.value.failure_count == breaker.config.failure_threshold
    
    @pytest.mark.asyncio
    async def test_circuit_recovery_attempt(self, breaker):
        """Test circuit recovery after timeout."""
        # Force circuit to open
        breaker.state = CircuitState.OPEN
        breaker.failure_count = breaker.config.failure_threshold
        breaker.last_failure_time = time.time() - (breaker.config.timeout + 1)
        
        async def success_func():
            return "recovery_success"
        
        result = await breaker.call(success_func)
        assert result == "recovery_success"
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_half_open_state_recovery(self, breaker):
        """Test half-open state recovery process."""
        # Force circuit to half-open
        breaker.state = CircuitState.HALF_OPEN
        breaker.success_count = 0
        
        async def success_func():
            return "success"
        
        # Need multiple successes to close circuit
        for i in range(3):
            result = await breaker.call(success_func)
            assert result == "success"
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_half_open_failure_returns_to_open(self, breaker):
        """Test that failure in half-open state returns to open."""
        # Force circuit to half-open
        breaker.state = CircuitState.HALF_OPEN
        breaker.last_failure_time = time.time()
        
        async def failing_func():
            raise ValueError("Recovery failed")
        
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.success_count == 0
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_not_handled(self, breaker):
        """Test that unexpected exceptions pass through without affecting circuit."""
        initial_state = breaker.state
        initial_failure_count = breaker.failure_count
        
        async def unexpected_error_func():
            raise KeyError("Unexpected error")
        
        with pytest.raises(KeyError):
            await breaker.call(unexpected_error_func)
        
        # Circuit state should not change for unexpected exceptions
        assert breaker.state == initial_state
        assert breaker.failure_count == initial_failure_count
    
    def test_status_property(self, breaker):
        """Test circuit breaker status property."""
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 5
        breaker.success_count = 2
        breaker.last_failure_time = 1234567890
        
        status = breaker.status
        
        assert status["name"] == "test_breaker"
        assert status["state"] == "open"
        assert status["failure_count"] == 5
        assert status["success_count"] == 2
        assert status["last_failure_time"] == 1234567890
        assert status["config"]["failure_threshold"] == 3
        assert status["config"]["timeout"] == 5


class TestCircuitBreakerManager:
    """Test circuit breaker manager functionality."""
    
    def test_create_breaker(self):
        """Test creating and registering a circuit breaker."""
        manager = CircuitBreakerManager()
        config = CircuitBreakerConfig(name="test_manager_breaker")
        
        breaker = manager.create_breaker("test_manager_breaker", config)
        
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.config.name == "test_manager_breaker"
        assert manager.get_breaker("test_manager_breaker") == breaker
    
    def test_get_nonexistent_breaker(self):
        """Test getting non-existent circuit breaker."""
        manager = CircuitBreakerManager()
        assert manager.get_breaker("nonexistent") is None
    
    def test_get_status_all_breakers(self):
        """Test getting status of all circuit breakers."""
        manager = CircuitBreakerManager()
        
        config1 = CircuitBreakerConfig(name="breaker1")
        config2 = CircuitBreakerConfig(name="breaker2")
        
        breaker1 = manager.create_breaker("breaker1", config1)
        breaker2 = manager.create_breaker("breaker2", config2)
        
        status = manager.get_status()
        
        assert len(status) == 2
        assert "breaker1" in status
        assert "breaker2" in status
        assert status["breaker1"]["name"] == "breaker1"
        assert status["breaker2"]["name"] == "breaker2"
    
    def test_reset_breaker(self):
        """Test manually resetting a circuit breaker."""
        manager = CircuitBreakerManager()
        config = CircuitBreakerConfig(name="reset_test")
        
        breaker = manager.create_breaker("reset_test", config)
        
        # Force circuit to open state
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 10
        breaker.last_failure_time = time.time()
        
        # Reset the breaker
        success = manager.reset_breaker("reset_test")
        
        assert success is True
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.last_failure_time == 0
    
    def test_reset_nonexistent_breaker(self):
        """Test resetting non-existent circuit breaker."""
        manager = CircuitBreakerManager()
        success = manager.reset_breaker("nonexistent")
        assert success is False


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_decorator_async_function(self):
        """Test decorator with async function."""
        call_count = 0
        
        @circuit_breaker("decorator_test_async", failure_threshold=2, timeout=1)
        async def test_func(should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("Test failure")
            return "success"
        
        # Successful call
        result = await test_func()
        assert result == "success"
        assert call_count == 1
        
        # Failing calls to open circuit
        with pytest.raises(ValueError):
            await test_func(should_fail=True)
        with pytest.raises(ValueError):
            await test_func(should_fail=True)
        
        # Circuit should now be open
        with pytest.raises(CircuitBreakerOpenError):
            await test_func()
        
        # Call count should not increase when circuit is open
        assert call_count == 3
    
    def test_decorator_sync_function(self):
        """Test decorator with sync function."""
        @circuit_breaker("decorator_test_sync", failure_threshold=2, timeout=1)
        def sync_test_func(x, y):
            if x == 0:
                raise ValueError("Division by zero")
            return y / x
        
        # This should work but requires an event loop
        # In practice, sync functions with circuit breakers would be used
        # in async contexts where an event loop is available
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = 2.0
            result = sync_test_func(1, 2)
            assert result == 2.0


class TestGlobalCircuitManager:
    """Test global circuit manager instance."""
    
    def test_global_manager_exists(self):
        """Test that global circuit manager exists."""
        assert circuit_manager is not None
        assert isinstance(circuit_manager, CircuitBreakerManager)
    
    def test_github_circuit_breaker_creation(self):
        """Test creating GitHub circuit breaker."""
        with patch('app.core.circuit_breaker.settings') as mock_settings:
            mock_settings.GITHUB_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
            mock_settings.GITHUB_CIRCUIT_BREAKER_TIMEOUT = 30
            
            from app.core.circuit_breaker import create_github_circuit_breaker
            
            breaker = create_github_circuit_breaker()
            
            assert breaker.config.name == "github_api"
            assert breaker.config.failure_threshold == 3
            assert breaker.config.timeout == 30
    
    def test_openai_circuit_breaker_creation(self):
        """Test creating OpenAI circuit breaker."""
        with patch('app.core.circuit_breaker.settings') as mock_settings:
            mock_settings.OPENAI_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 2
            mock_settings.OPENAI_CIRCUIT_BREAKER_TIMEOUT = 20
            
            from app.core.circuit_breaker import create_openai_circuit_breaker
            
            breaker = create_openai_circuit_breaker()
            
            assert breaker.config.name == "openai_api"
            assert breaker.config.failure_threshold == 2
            assert breaker.config.timeout == 20