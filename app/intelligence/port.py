from abc import ABC, abstractmethod


class IntelligencePort(ABC):
    """
    Define la interfaz que cualquier servicio de inteligencia artificial
    debe cumplir para evaluar proyectos.
    """

    @abstractmethod
    async def evaluate_project(self, project: dict) -> dict:
        """
        Evalúa un proyecto y debe retornar un diccionario con dos claves:
        - "should_propose": bool
        - "reason": str
        """
        pass
