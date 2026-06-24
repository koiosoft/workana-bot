import os
from .port import IntelligencePort
from .adapters.gemini import GeminiAdapter
from .adapters.openrouter import OpenRouterAdapter
from loguru import logger

_instance: IntelligencePort | None = None


def get_intelligence_service() -> IntelligencePort:
    """
    Retorna una instancia singleton del servicio de inteligencia,
    seleccionando el proveedor desde las variables de entorno.
    """
    global _instance
    if _instance is None:
        provider = os.getenv("AI_PROVIDER", "gemini").lower()
        logger.info(f"🤖 Proveedor de IA seleccionado: '{provider}'")

        if provider == "gemini":
            _instance = GeminiAdapter()
        elif provider == "openrouter":
            _instance = OpenRouterAdapter()
        # Futuro: Añadir otros proveedores como "openai" o un "dummy" para pruebas
        # elif provider == "dummy":
        #     _instance = DummyIntelligenceAdapter()
        else:
            logger.error(f"Proveedor de IA desconocido: {provider}")
            raise ValueError(f"Proveedor de IA desconocido: {provider}")

    return _instance
