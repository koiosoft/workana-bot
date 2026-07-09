from dataclasses import dataclass
from typing import Any, Optional

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

    The returned adapter exposes :meth:`IntelligencePort.refine_proposal`
    for refining proposals with a user-specified LLM model.
    """
    global _instances
    if "STANDARD" not in _instances:
        await create_intelligence_service(db)
    return _instances["STANDARD"]


def select_initial_proposal_template(contract_type: str) -> str:
    """Return the initial proposal template name for a given contract type.

    Args:
        contract_type: Either ``"project_fixed"`` or ``"staff_augmentation"``.

    Returns:
        ``"proposal.j2"`` for project-fixed, ``"proposal_staffing.j2"`` for
        staff augmentation.
    """
    if contract_type == "staff_augmentation":
        return "proposal_staffing.j2"
    return "proposal.j2"


async def refine_proposal(
    project: dict[str, Any],
    user_feedback_observations: str,
    model_id: str,
    contract_type: str | None = None,
    db: AsyncIOMotorDatabase | None = None,
) -> dict[str, Any]:
    """Refine a proposal using the correct intelligence adapter for the model.

    Looks up the requested *model_id* in the ``models`` collection to
    determine its provider, then routes the refinement request to the
    appropriate adapter.  Falls back to the STANDARD adapter when the
    model cannot be resolved (e.g. DB unavailable or model not found).

    When *contract_type* differs from the project's existing
    ``contract_type`` field, the adapter is instructed to use the
    initial proposal template instead of the refinement template,
    effectively regenerating the proposal from scratch with the new
    contract type.

    Args:
        project: The project dict (must include title, description,
            skills, budget_detail, and optionally the current proposal).
        user_feedback_observations: Free-text feedback guiding the
            refinement.
        model_id: OpenRouter or Gemini model identifier to use for
            generation.
        contract_type: Optional contract type override.  When provided
            and different from the project's existing value, the
            adapter uses the initial proposal template.
        db: Optional database handle forwarded to
            :func:`get_intelligence_service`.

    Returns:
        The LLM-generated refined proposal as a dict.
    """
    # -- Determine if contract type changed --------------------------------
    existing_contract_type: str = project.get("contract_type", "project_fixed")
    effective_contract_type: str = (
        contract_type if contract_type is not None else existing_contract_type
    )
    use_initial_template: bool = (
        contract_type is not None and contract_type != existing_contract_type
    )

    if use_initial_template:
        logger.info(
            f"🔄 Contract type change detected: "
            f"'{existing_contract_type}' → '{contract_type}' — "
            f"using initial proposal template"
        )

    # Determine which provider owns the requested model
    provider_key = await _resolve_provider_for_model(model_id, db)

    if provider_key:
        adapter = await _get_adapter_for_provider(provider_key, db)
        logger.info(
            f"🔀 Routing refine_proposal(model='{model_id}') "
            f"→ provider '{provider_key}'"
        )
    else:
        logger.warning(
            f"⚠️  Model '{model_id}' not found in DB — "
            f"falling back to STANDARD adapter with its default model"
        )
        adapter = await get_intelligence_service(db)
        model_id = ""  # Let the adapter use its own default model

    return await adapter.refine_proposal(
        project=project,
        user_feedback_observations=user_feedback_observations,
        model_id=model_id,
        contract_type=effective_contract_type,
        use_initial_template=use_initial_template,
    )


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


# ---------------------------------------------------------------------------
# Provider-aware routing for refine_proposal
# ---------------------------------------------------------------------------


async def _resolve_provider_for_model(
    model_id: str,
    db: AsyncIOMotorDatabase | None = None,
) -> str | None:
    """Look up the provider key for a given *model_id* in the DB.

    Returns ``None`` if the model is not found or the DB is unavailable.
    """
    if db is None:
        db = get_database()

    try:
        model_doc = await db["models"].find_one(
            {"model_id": model_id},
            {"provider_key": 1},
        )
        if model_doc:
            return model_doc.get("provider_key")
        return None
    except Exception as e:
        logger.warning(f"Could not resolve provider for model '{model_id}': {e}")
        return None


async def _get_adapter_for_provider(
    provider_key: str,
    db: AsyncIOMotorDatabase | None = None,
) -> IntelligencePort:
    """Return a cached adapter for *provider_key*, creating one if needed.

    Ensures the adapters cache is initialised first (via
    :func:`create_intelligence_service`).  If the requested provider
    happens to match an already-cached STANDARD/PREMIUM/FILTER adapter,
    that instance is reused.  Otherwise, a new adapter is created and
    cached under the provider key.
    """
    global _instances

    # Ensure the cache is populated
    if not _instances:
        await create_intelligence_service(db)

    # Check if we already cached an adapter for this exact provider_key
    if provider_key in _instances:
        return _instances[provider_key]

    # Check if the STANDARD adapter already uses this provider
    std_adapter = _instances.get("STANDARD")
    if std_adapter is not None:
        if (provider_key == "gemini" and isinstance(std_adapter, GeminiAdapter)) or \
           (provider_key == "openrouter" and isinstance(std_adapter, OpenRouterAdapter)):
            _instances[provider_key] = std_adapter
            return std_adapter

    # Also check PREMIUM adapter
    prm_adapter = _instances.get("PREMIUM")
    if prm_adapter is not None:
        if (provider_key == "gemini" and isinstance(prm_adapter, GeminiAdapter)) or \
           (provider_key == "openrouter" and isinstance(prm_adapter, OpenRouterAdapter)):
            _instances[provider_key] = prm_adapter
            return prm_adapter

    # Create a new adapter for this provider
    logger.info(f"🆕 Creating new adapter for provider '{provider_key}'")
    adapter = _create_adapter(provider_key, None)
    _instances[provider_key] = adapter
    return adapter
