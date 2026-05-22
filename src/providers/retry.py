"""
Retry Module
============
Retry strategies and circuit breaker for providers.
"""

import time
import asyncio
import functools
from typing import Callable, Any, Optional, Type, Tuple
from dataclasses import dataclass
from enum import Enum
from src.core.logger import get_logger

logger = get_logger(__name__)


class RetryStrategy:
    """Configurable retry strategy."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        if self.jitter:
            import random
            delay *= (0.5 + random.random())
        return delay


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern for provider resilience."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def record_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
        else:
            self.failure_count = 0

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self.failure_count >= self.failure_threshold:
            self._transition_to_open()

    def can_attempt(self) -> bool:
        """Check if an attempt can be made."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                self._transition_to_half_open()
                return True
            return False

        return True

    def _transition_to_open(self):
        """Transition to open state."""
        self.state = CircuitState.OPEN
        logger.warning("Circuit breaker opened")

    def _transition_to_closed(self):
        """Transition to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("Circuit breaker closed")

    def _transition_to_half_open(self):
        """Transition to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.info("Circuit breaker half-open")


def with_retry(
    strategy: Optional[RetryStrategy] = None,
    circuit_breaker: Optional[CircuitBreaker] = None
):
    """Decorator to add retry and circuit breaker to a function."""
    if strategy is None:
        strategy = RetryStrategy()

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if circuit_breaker and not circuit_breaker.can_attempt():
                    raise Exception("Circuit breaker is open")

                last_exception = None
                for attempt in range(strategy.max_attempts):
                    try:
                        result = await func(*args, **kwargs)
                        if circuit_breaker:
                            circuit_breaker.record_success()
                        return result
                    except strategy.exceptions as e:
                        last_exception = e
                        if circuit_breaker:
                            circuit_breaker.record_failure()

                        if attempt < strategy.max_attempts - 1:
                            delay = strategy.calculate_delay(attempt)
                            logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                        else:
                            logger.error(f"All attempts failed for {func.__name__}")

                raise last_exception
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if circuit_breaker and not circuit_breaker.can_attempt():
                    raise Exception("Circuit breaker is open")

                last_exception = None
                for attempt in range(strategy.max_attempts):
                    try:
                        result = func(*args, **kwargs)
                        if circuit_breaker:
                            circuit_breaker.record_success()
                        return result
                    except strategy.exceptions as e:
                        last_exception = e
                        if circuit_breaker:
                            circuit_breaker.record_failure()

                        if attempt < strategy.max_attempts - 1:
                            delay = strategy.calculate_delay(attempt)
                            logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {delay:.2f}s")
                            time.sleep(delay)
                        else:
                            logger.error(f"All attempts failed for {func.__name__}")

                raise last_exception
            return sync_wrapper
    return decorator