
class AIConnectionError(Exception):
    """Custom exception for AI API connection errors."""
    pass

class CircuitBreakerError(Exception):
    """Base exception for circuit breaker state changes."""
    def __init__(self, message, failures: int, backoff: int = 0):
        self.failures = failures
        self.backoff_duration = backoff
        super().__init__(message)

class CircuitBreakerWarning(CircuitBreakerError):
    """Raised on the 2nd consecutive failure."""
    pass

class CircuitBreakerSuspension(CircuitBreakerError):
    """Raised on the 3rd consecutive failure."""
    pass

class CircuitBreakerCritical(CircuitBreakerError):
    """Raised on the 4th consecutive failure."""
    pass

class CircuitBreakerTrippedError(CircuitBreakerError):
    """Raised for definitive shutdown after max failures."""
    pass
