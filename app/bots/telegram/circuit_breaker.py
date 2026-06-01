from loguru import logger
from app.exceptions import (
    CircuitBreakerWarning,
    CircuitBreakerSuspension,
    CircuitBreakerCritical,
    CircuitBreakerTrippedError,
)

class CircuitBreaker:
    """
    Manages the state of the connection to the AI API, implementing a phased
    circuit breaker to handle persistent failures.
    """
    
    # Phased backoff configuration (failures -> minutes)
    BACKOFF_PHASES = {
        2: ("Alerta Temprana", 5, CircuitBreakerWarning),
        3: ("Suspensión Prolongada", 10, CircuitBreakerSuspension),
        4: ("Espera Crítica", 20, CircuitBreakerCritical),
    }
    TRIP_THRESHOLD = 5  # Apagado definitivo

    def __init__(self):
        self._consecutive_failures = 0
        logger.info("Circuit Breaker inicializado.")

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def record_success(self):
        """Resets the failure counter after a successful API call."""
        if self._consecutive_failures > 0:
            logger.success(
                f"La API de IA se ha recuperado tras {self._consecutive_failures} fallas consecutivas. "
                "El contador del Circuit Breaker se ha reseteado."
            )
            self._consecutive_failures = 0

    def record_failure(self):
        """
        Increments the failure counter and may raise a CircuitBreaker exception
        if a threshold is reached.
        """
        self._consecutive_failures += 1
        logger.warning(
            f"Falla consecutiva de la API de IA registrada. Total: {self._consecutive_failures}."
        )

        # Check for definitive shutdown
        if self._consecutive_failures >= self.TRIP_THRESHOLD:
            message = (
                f"Apagado Definitivo: Se alcanzó el umbral de {self.TRIP_THRESHOLD} fallas consecutivas."
            )
            logger.critical(message)
            raise CircuitBreakerTrippedError(message, failures=self._consecutive_failures)

        # Check for phased backoff
        if self._consecutive_failures in self.BACKOFF_PHASES:
            phase_name, backoff, exception_class = self.BACKOFF_PHASES[self._consecutive_failures]
            message = (
                f"{phase_name}: {self._consecutive_failures} fallas consecutivas. "
                f"Iniciando backoff de {backoff} minutos."
            )
            logger.warning(message)
            raise exception_class(message, failures=self._consecutive_failures, backoff=backoff)

