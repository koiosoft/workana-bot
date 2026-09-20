from abc import ABC, abstractmethod
from typing import Any, Optional
# Se usa TYPE_CHECKING para evitar importaciones circulares en runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bots.telegram.circuit_breaker import CircuitBreaker


class IntelligencePort(ABC):
    """
    Define la interfaz que cualquier servicio de inteligencia artificial
    debe cumplir para evaluar proyectos.
    """


    @abstractmethod
    async def evaluate_projects(
        self, projects: list[dict[str, Any]], circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> list[dict[str, Any]]:
        """Evalúa una lista de proyectos y devuelve decisiones individuales."""
        pass

    @abstractmethod
    async def generate_proposal(
        self, project: dict, circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def refine_proposal(
        self,
        project: dict[str, Any],
        user_feedback_observations: str,
        model_id: str,
        contract_type: str = "project_fixed",
        use_initial_template: bool = False,
        circuit_breaker: Optional["CircuitBreaker"] = None,
    ) -> dict[str, Any]:
        """Refina una propuesta existente usando feedback del usuario."""
        pass

    @abstractmethod
    async def format_project_description(
        self, description: str, circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> str:
        """Formatea la descripción de un proyecto para mejorar su legibilidad."""
        pass

    @abstractmethod
    async def analyze_requirement(
        self,
        project: dict,
        maturity_threshold: int = 8,
        circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> dict[str, Any]:
        """Analiza el requerimiento del proyecto usando el pipeline por etapas."""
        pass

    @abstractmethod
    async def estimate_technical(
        self,
        project: dict,
        analysis: dict,
        circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> dict[str, Any]:
        """Estima técnicamente el proyecto basado en el análisis de requerimientos."""
        pass

    @abstractmethod
    async def write_commercial_proposal(
        self,
        project: dict,
        technical_estimate: dict,
        circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> dict[str, Any]:
        """Escribe la propuesta comercial basada en la estimación técnica."""
        pass