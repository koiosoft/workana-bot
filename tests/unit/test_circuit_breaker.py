import pytest
from app.bots.telegram.circuit_breaker import CircuitBreaker
from app.exceptions import (
    CircuitBreakerError,
    CircuitBreakerWarning,
    CircuitBreakerSuspension,
    CircuitBreakerCritical,
    CircuitBreakerTrippedError,
)

def test_circuit_breaker_initial_state():
    cb = CircuitBreaker()
    assert cb.consecutive_failures == 0

def test_circuit_breaker_increments_failures():
    cb = CircuitBreaker()
    cb.record_failure()
    assert cb.consecutive_failures == 1

def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker()
    try:
        cb.record_failure()
        # This second call will raise a warning, but we catch it to test the reset
        cb.record_failure()
    except CircuitBreakerError:
        pass
    assert cb.consecutive_failures == 2
    cb.record_success()
    assert cb.consecutive_failures == 0

def test_circuit_breaker_does_nothing_on_first_failure():
    cb = CircuitBreaker()
    # No exception should be raised
    cb.record_failure()
    assert cb.consecutive_failures == 1

def test_circuit_breaker_raises_warning_on_second_failure():
    cb = CircuitBreaker()
    cb.record_failure()
    with pytest.raises(CircuitBreakerWarning) as excinfo:
        cb.record_failure()
    assert cb.consecutive_failures == 2
    assert excinfo.value.failures == 2
    assert excinfo.value.backoff_duration == 5

def test_circuit_breaker_raises_suspension_on_third_failure():
    cb = CircuitBreaker()
    # Ingest first 2 failures, ignoring the exceptions they raise
    for _ in range(2):
        try:
            cb.record_failure()
        except CircuitBreakerError:
            pass
            
    with pytest.raises(CircuitBreakerSuspension) as excinfo:
        cb.record_failure()
    assert cb.consecutive_failures == 3
    assert excinfo.value.failures == 3
    assert excinfo.value.backoff_duration == 10

def test_circuit_breaker_raises_critical_on_fourth_failure():
    cb = CircuitBreaker()
    for _ in range(3):
        try:
            cb.record_failure()
        except CircuitBreakerError:
            pass

    with pytest.raises(CircuitBreakerCritical) as excinfo:
        cb.record_failure()
    assert cb.consecutive_failures == 4
    assert excinfo.value.failures == 4
    assert excinfo.value.backoff_duration == 20

def test_circuit_breaker_trips_on_fifth_failure():
    cb = CircuitBreaker()
    for _ in range(4):
        try:
            cb.record_failure()
        except CircuitBreakerError:
            pass
            
    with pytest.raises(CircuitBreakerTrippedError) as excinfo:
        cb.record_failure()
    assert cb.consecutive_failures == 5
    assert excinfo.value.failures == 5

def test_circuit_breaker_resets_after_warning():
    cb = CircuitBreaker()
    cb.record_failure()
    try:
        cb.record_failure()
    except CircuitBreakerWarning:
        pass
    assert cb.consecutive_failures == 2
    cb.record_success()
    assert cb.consecutive_failures == 0
