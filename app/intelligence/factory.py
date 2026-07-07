import os
from dataclasses import dataclass
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from .port import IntelligencePort
from .adapters.gemini import GeminiAdapter
from .adapters.openrouter import OpenRouterAdapter
from app.database.mongo import get_database
from loguru import logger


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ModelInfo:
    """Resolved default-model information retrieved from MongoDB.

    Attributes:
        model_id: Provider-specific model identifier (e.g.
            ``'models/gemini-2.5-flash'``).  An empty string signals
            "use the adapter's hardcoded default".
        provider_key: Unique provider key (``'gemini'`` or
            ``'openrouter'``) that determines which adapter class to
            instantiate.  Matches the ``key`` field in the
            ``providers`` collection.
    """
    model_id: str
    provider_key: str


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DefaultModelNotFoundError(Exception):
    """Raised when one or more required default models are missing from
    the ``models`` collection."""


class ModelsCollectionUnavailableError(Exception):
    """Raised when the ``models`` collection cannot be accessed (e.g.
    MongoDB connection failure)."""


# ---------------------------------------------------------------------------
# Cached adapter instances (STANDARD, PREMIUM, FILTER)
# ---------------------------------------------------------------------------

_instances: dict[str, IntelligencePort] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_intelligence_service(
    db: AsyncIOMotorDatabase | None = None,
) -> IntelligencePort:
    """Return the **STANDARD** intelligence service adapter (cached).

    Delegates to :func:`create_intelligence_service` on first call to
    initialise all three adapters from the database.  Subsequent calls
    return the previously cached instance immediately.
    """
    global _instances
    if "STANDARD" not in _instances:
        await create_intelligence_service(db)
    return _instances["STANDARD"]


def get_intelligence_adapters() -> dict[str, IntelligencePort] | None:
    """Return the cached adapters dict *without* triggering DB queries.

    Returns ``None`` when :func:`create_intelligence_service` has not been
    called yet.  Use :func:`get_intelligence_service` or
    :func:`create_intelligence_service` to populate the cache first.
    """
    return _instances if _instances else None


# ---------------------------------------------------------------------------
# Database-driven model resolution
# ---------------------------------------------------------------------------

async def get_default_models_from_db(
    db: AsyncIOMotorDatabase | None = None,
) -> tuple[ModelInfo, ModelInfo]:
    """Query the ``models`` collection for the two default models.

    The ``models`` collection is expected to hold **exactly two**
    default entries (see :class:`~app.models.models.Model`):

    * **STANDARD** — ``is_default=True``, ``is_premium=False``.
      This model handles both project evaluation and description
      filtering (the FILTER adapter shares the same model).
    * **PREMIUM** — ``is_default=True``, ``is_premium=True``.
      Used exclusively for proposal generation.

    Each document's ``provider_key`` field (matching
    ``providers.key`` — see :class:`~app.models.provider.ProviderModel`)
    determines which adapter class is instantiated later.

    Returns:
        ``(standard_info, premium_info)`` where each
        :class:`ModelInfo` carries the resolved ``model_id`` and
        ``provider_key``.

    Raises:
        DefaultModelNotFoundError: when either default model is
            missing from the collection.
        ModelsCollectionUnavailableError: when the database connection
            fails or the collection cannot be queried.
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

        missing: list[str] = []
        if not default_standard:
            missing.append("STANDARD (is_default=True, is_premium=False)")
        if not default_premium:
            missing.append("PREMIUM (is_default=True, is_premium=True)")

        if missing:
            raise DefaultModelNotFoundError(
                f"Missing default models in DB: {', '.join(missing)}"
            )

        standard_info = ModelInfo(
            model_id=default_standard["model_id"],
            provider_key=default_standard.get("provider_key", "gemini"),
        )
        premium_info = ModelInfo(
            model_id=default_premium["model_id"],
            provider_key=default_premium.get("provider_key", "gemini"),
        )

        logger.info(
            f"📦 Default models from DB: "
            f"standard={standard_info.model_id} (via {standard_info.provider_key}), "
            f"premium={premium_info.model_id} (via {premium_info.provider_key})"
        )
        return standard_info, premium_info

    except DefaultModelNotFoundError:
        raise
    except Exception as e:
        raise ModelsCollectionUnavailableError(
            f"Could not query models collection: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Adapter instantiation
# ---------------------------------------------------------------------------


def _create_adapter(
    provider_key: str,
    model_id: str | None,
) -> IntelligencePort:
    """Instantiate the correct adapter class for *provider_key*.

    All three model overrides (standard, premium, filter) receive the
    same *model_id* so the adapter always routes through its dedicated
    tier model regardless of internal strategy selection.
    """
    if provider_key == "gemini":
        return GeminiAdapter(
            standard_model=model_id,
            premium_model=model_id,
            filter_model=model_id,
        )
    if provider_key == "openrouter":
        return OpenRouterAdapter(
            standard_model=model_id,
            premium_model=model_id,
            filter_model=model_id,
        )

    raise ValueError(
        f"Unknown AI provider key: '{provider_key}'. "
        f"Expected 'gemini' or 'openrouter'."
    )


async def create_intelligence_service(
    db: AsyncIOMotorDatabase | None = None,
) -> dict[str, IntelligencePort]:
    """Create and cache all three intelligence service adapters.

    Reads the ``models`` collection to find the default STANDARD and
    PREMIUM models.  Each model's ``provider_key`` determines which
    adapter class is instantiated, allowing STANDARD and PREMIUM to
    be served by different providers.

    * **STANDARD** adapter → standard model from DB (any provider).
    * **PREMIUM** adapter → premium model from DB (any provider).
    * **FILTER** adapter → same model as STANDARD (non-transactional
      filtering uses the fast/cheap standard model).

    Returns:
        ``{"STANDARD": ..., "PREMIUM": ..., "FILTER": ...}``.

    Falls back to hardcoded Gemini defaults **only** when MongoDB
    is unavailable or default models are missing.
    """
    global _instances
    if _instances:
        return _instances

    try:
        standard_info, premium_info = await get_default_models_from_db(db)
    except ModelsCollectionUnavailableError as e:
        logger.warning(f"{e} — falling back to hardcoded Gemini defaults")
        standard_info = ModelInfo(model_id="", provider_key="gemini")
        premium_info = ModelInfo(model_id="", provider_key="gemini")
    except DefaultModelNotFoundError as e:
        logger.warning(f"{e} — falling back to hardcoded Gemini defaults")
        standard_info = ModelInfo(model_id="", provider_key="gemini")
        premium_info = ModelInfo(model_id="", provider_key="gemini")

    # STANDARD adapter — uses the standard model's provider
    _instances["STANDARD"] = _create_adapter(
        standard_info.provider_key,
        standard_info.model_id or None,
    )

    # PREMIUM adapter — uses the premium model's provider (may differ!)
    _instances["PREMIUM"] = _create_adapter(
        premium_info.provider_key,
        premium_info.model_id or None,
    )

    # FILTER adapter — shares the standard model (filtering is non-transactional)
    _instances["FILTER"] = _create_adapter(
        standard_info.provider_key,
        standard_info.model_id or None,
    )

    logger.info(
        f"✅ Adapters initialised: "
        f"STANDARD [{standard_info.provider_key}], "
        f"PREMIUM [{premium_info.provider_key}], "
        f"FILTER [{standard_info.provider_key}]"
    )
    return _instances
