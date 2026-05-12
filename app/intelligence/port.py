from abc import ABC, abstractmethod
from typing import Any


class IntelligencePort(ABC):
    """
    Define la interfaz que cualquier servicio de inteligencia artificial
    debe cumplir para evaluar proyectos.
    """


    @abstractmethod
    async def evaluate_projects(self, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Evalúa una lista de proyectos y devuelve decisiones individuales."""
        pass

    @abstractmethod
    async def generate_proposal(self, project: dict) -> dict[str, Any]:
        pass