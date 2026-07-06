import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from .port import IntelligencePort
from .adapters.gemini import GeminiAdapter
from .adapters.openrouter import OpenRouterAdapter
from app.database.mongo import get_database
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


# ---------------------------------------------------------------------------
# Database-driven model resolution
# ---------------------------------------------------------------------------

async def get_default_models_from_db(
    db: AsyncIOMotorDatabase | None = None,
) -> tuple[str, str]:
    """Query the ``models`` collection for the current default models.

    Returns:
        (standard_model_id, premium_model_id)

    Falls back to adapter-level hardcoded constants if the collection
    is empty or unavailable.
    """
    if db is None:
        db = get_database()

    try:
        default_standard = await db["models"].find_one(
            {"is_default": True, "is_premium": False}
        )
        default_premium = await db["models"].find_one(
            {"is_default": True, "is_premium": True}
        )

        standard_id: str = (
            default_standard["model_id"]
            if default_standard
            else OpenRouterAdapter.__module__  # won't be used; see below
        )
        premium_id: str = (
            default_premium["model_id"]
            if default_premium
            else ""
        )

        if default_standard and default_premium:
            logger.info(
                f"📦 Default models from DB: standard={standard_id}, premium={premium_id}"
            )
            return standard_id, premium_id

        logger.warning("Default models not found in DB — falling back to adapter constants")
    except Exception as e:
        logger.warning(f"Could not query models collection: {e} — falling back to adapter constants")

    return "", ""  # empty signals to adapters "use your own hardcoded default"


async def create_intelligence_service(
    db: AsyncIOMotorDatabase | None = None,
) -> IntelligencePort:
    """Create an intelligence service instance using model IDs from the database.

    Reads the ``models`` collection to find the default standard and premium
    model IDs and injects them into the adapter, overriding the hardcoded
    constants in each adapter module.

    Falls back to adapter-level defaults when the DB is not available.
    """
    global _instance
    if _instance is not None:
        return _instance

    standard_model_id, premium_model_id = await get_default_models_from_db(db)

    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    logger.info(f"🤖 Proveedor de IA seleccionado: '{provider}'")

    if provider == "gemini":
        _instance = GeminiAdapter(
            standard_model=standard_model_id or None,
            premium_model=premium_model_id or None,
        )
    elif provider == "openrouter":
        _instance = OpenRouterAdapter(
            standard_model=standard_model_id or None,
            premium_model=premium_model_id or None,
        )
    else:
        logger.error(f"Proveedor de IA desconocido: {provider}")
        raise ValueError(f"Proveedor de IA desconocido: {provider}")

    return _instance
