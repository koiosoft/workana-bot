"""Models & Providers API Routes.

Endpoints:
  - GET /api/models/providers       : list all providers
  - GET /api/models                 : list models, optionally filtered by tier
"""

from fastapi import APIRouter, Body, Path, Query, HTTPException
from typing import Optional
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from app.database.mongo import get_database
from app.models.provider import ProviderModel
from app.models.model import ModelModel
from loguru import logger

router = APIRouter(tags=["models"])


class ProviderUpdate(BaseModel):
    """Payload for updating an existing model provider."""

    name: Optional[str] = Field(None, min_length=1, description="Human-readable provider name")
    url: Optional[str] = Field(None, min_length=1, description="Provider's base URL")


class ModelUpdate(BaseModel):
    """Payload for updating model flags."""

    is_default: Optional[bool] = Field(None, description="Whether this model is a default selection for its tier")
    is_premium: Optional[bool] = Field(None, description="Whether this model belongs to the premium tier")


@router.put("/providers/{provider_key}")
async def update_provider(
    provider_key: str = Path(..., min_length=1, description="Unique provider key"),
    update_data: ProviderUpdate = Body(..., description="Fields to update"),
) -> dict:
    """Update an existing model provider.

    Allows partial updates to ``name`` and/or ``url``.
    Returns 404 if the provider does not exist.
    """
    db = get_database()

    existing = await db["providers"].find_one({"key": provider_key})
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not Found",
                "message": f"Provider with key '{provider_key}' not found.",
            },
        )

    # Build update dict with only non-None fields
    update_fields = update_data.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "No valid fields provided for update.",
            },
        )

    try:
        result = await db["providers"].update_one(
            {"key": provider_key},
            {"$set": update_fields},
        )
        logger.info(f"Provider updated: key='{provider_key}', fields={list(update_fields.keys())}")
    except Exception as e:
        logger.error(f"Unexpected error updating provider '{provider_key}': {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while updating the provider.",
                "details": str(e),
            },
        )

    # Fetch and return the updated provider
    updated = await db["providers"].find_one({"key": provider_key}, {"_id": 0})
    return updated


@router.delete("/providers/{provider_key}")
async def delete_provider(
    provider_key: str = Path(..., min_length=1, description="Unique provider key"),
) -> dict:
    """Soft-delete a model provider and cascade to associated models.

    Sets ``is_deleted: True`` on the provider and all models referencing
    its ``provider_key``. The data is preserved for historical records.
    Returns 404 if the provider does not exist.
    """
    db = get_database()

    existing = await db["providers"].find_one({"key": provider_key})
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not Found",
                "message": f"Provider with key '{provider_key}' not found.",
            },
        )

    try:
        # Soft-delete the provider
        await db["providers"].update_one(
            {"key": provider_key},
            {"$set": {"is_deleted": True}},
        )

        # Cascade: soft-delete all associated models
        cascade_result = await db["models"].update_many(
            {"provider_key": provider_key},
            {"$set": {"is_deleted": True}},
        )

        logger.info(
            f"Provider soft-deleted: key='{provider_key}', "
            f"cascaded to {cascade_result.modified_count} model(s)"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error deleting provider '{provider_key}': {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while deleting the provider.",
                "details": str(e),
            },
        )

    return {
        "message": f"Provider '{provider_key}' and associated models soft-deleted successfully.",
        "cascaded_models": cascade_result.modified_count,
    }


@router.get("/providers")
async def list_providers() -> list[dict]:
    """Return all registered AI model providers."""
    db = get_database()
    cursor = db["providers"].find({}, {"_id": 0})
    providers = await cursor.to_list(length=100)
    return providers


@router.post("/providers", status_code=201)
async def create_provider(
    provider: ProviderModel = Body(..., description="Model provider to create"),
) -> dict:
    """Create a new AI model provider.

    Validates the input against the ProviderModel Pydantic schema.
    Inserts the provider into the ``providers`` collection.
    Returns a 409 Conflict if a provider with the same key already exists.
    """
    db = get_database()
    provider_dict = provider.model_dump()

    try:
        result = await db["providers"].insert_one(provider_dict)
        logger.info(f"Provider created: key='{provider.key}', id={result.inserted_id}")
    except DuplicateKeyError:
        logger.warning(f"Duplicate provider key attempted: '{provider.key}'")
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Conflict",
                "message": f"A provider with key '{provider.key}' already exists.",
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error creating provider '{provider.key}': {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while creating the provider.",
                "details": str(e),
            },
        )

    provider_dict["_id"] = str(result.inserted_id)
    return provider_dict


@router.post("", status_code=201)
async def create_model(
    model: ModelModel = Body(..., description="LLM model to create"),
) -> dict:
    """Create a new LLM model entry.

    Validates the input against the ModelModel Pydantic schema.
    Ensures the referenced ``provider_key`` exists before insertion.
    Returns a 409 Conflict if a model with the same (model_id, provider_key)
    combination already exists.
    """
    db = get_database()

    # Verify the provider exists
    provider = await db["providers"].find_one({"key": model.provider_key})
    if provider is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": f"Provider with key '{model.provider_key}' does not exist.",
            },
        )

    model_dict = model.model_dump()

    try:
        result = await db["models"].insert_one(model_dict)
        logger.info(
            f"Model created: model_id='{model.model_id}', "
            f"provider='{model.provider_key}', id={result.inserted_id}"
        )
    except DuplicateKeyError:
        logger.warning(
            f"Duplicate model attempted: model_id='{model.model_id}', "
            f"provider='{model.provider_key}'"
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Conflict",
                "message": (
                    f"A model with model_id '{model.model_id}' and "
                    f"provider_key '{model.provider_key}' already exists."
                ),
            },
        )
    except Exception as e:
        logger.error(
            f"Unexpected error creating model '{model.model_id}': {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while creating the model.",
                "details": str(e),
            },
        )

    model_dict["_id"] = str(result.inserted_id)
    return model_dict


@router.put("/{model_id}")
async def update_model(
    model_id: str = Path(..., min_length=1, description="Unique model identifier"),
    update_data: ModelUpdate = Body(..., description="Flags to update"),
) -> dict:
    """Update model flags (is_default, is_premium).

    When setting ``is_default=True``, the endpoint ensures mutual exclusion:
    it unsets ``is_default`` on all other models in the same tier (premium or
    standard), guaranteeing at most one default per tier.

    Returns 404 if the model does not exist.
    """
    db = get_database()

    existing = await db["models"].find_one({"model_id": model_id})
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not Found",
                "message": f"Model with id '{model_id}' not found.",
            },
        )

    # Determine the tier for mutual exclusion:
    # use the update's is_premium if provided, otherwise keep current value
    new_is_premium = (
        update_data.is_premium
        if update_data.is_premium is not None
        else existing.get("is_premium", False)
    )
    new_is_default = (
        update_data.is_default
        if update_data.is_default is not None
        else existing.get("is_default", False)
    )

    update_fields: dict = {}
    if update_data.is_default is not None:
        update_fields["is_default"] = new_is_default
    if update_data.is_premium is not None:
        update_fields["is_premium"] = new_is_premium

    if not update_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Bad Request",
                "message": "No valid fields provided for update.",
            },
        )

    # Mutual exclusion: if setting is_default to True, unset others in the same tier
    if new_is_default:
        await db["models"].update_many(
            {
                "model_id": {"$ne": model_id},
                "is_premium": new_is_premium,
                "is_default": True,
            },
            {"$set": {"is_default": False}},
        )
        logger.info(
            f"Mutual exclusion applied: unset is_default on other "
            f"{'premium' if new_is_premium else 'standard'} models"
        )

    try:
        result = await db["models"].update_one(
            {"model_id": model_id},
            {"$set": update_fields},
        )
        logger.info(
            f"Model updated: model_id='{model_id}', "
            f"fields={list(update_fields.keys())}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error updating model '{model_id}': {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while updating the model.",
                "details": str(e),
            },
        )

    updated = await db["models"].find_one({"model_id": model_id}, {"_id": 0})
    return updated


@router.delete("/{model_id}")
async def delete_model(
    model_id: str = Path(..., min_length=1, description="Unique model identifier"),
) -> dict:
    """Soft-delete an LLM model, preserving historical usage records.

    Sets ``is_deleted: True`` on the model document. The data is retained
    for historical and audit purposes.
    Returns 404 if the model does not exist.
    """
    db = get_database()

    existing = await db["models"].find_one({"model_id": model_id})
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not Found",
                "message": f"Model with id '{model_id}' not found.",
            },
        )

    try:
        await db["models"].update_one(
            {"model_id": model_id},
            {"$set": {"is_deleted": True}},
        )
        logger.info(f"Model soft-deleted: model_id='{model_id}'")
    except Exception as e:
        logger.error(
            f"Unexpected error deleting model '{model_id}': {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred while deleting the model.",
                "details": str(e),
            },
        )

    return {"message": f"Model '{model_id}' soft-deleted successfully."}


@router.get("")
async def list_models(
    model_filter: Optional[str] = Query(
        None,
        alias="filter",
        description="Filter by tier: 'standard' (is_premium=false) or 'premium' (is_premium=true)",
    ),
) -> list[dict]:
    """Return models with provider brand information.

    Supports an optional ``filter`` query parameter:
      - ``standard`` → return only non-premium models
      - ``premium``  → return only premium models
      - omitted      → return all models

    Each result is enriched with the provider's ``name`` (brand) and ``url``
    via a lookup on the ``providers`` collection.
    """
    db = get_database()

    # Build query
    query: dict = {}
    if model_filter is not None:
        flt = model_filter.strip().lower()
        if flt == "standard":
            query["is_premium"] = False
        elif flt == "premium":
            query["is_premium"] = True
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter value '{model_filter}'. Use 'standard' or 'premium'.",
            )

    # Fetch models
    cursor = db["models"].find(query, {"_id": 0})
    models = await cursor.to_list(length=200)

    # Enrich with provider brand/name
    if models:
        provider_keys = {m["provider_key"] for m in models if "provider_key" in m}
        if provider_keys:
            providers_cursor = db["providers"].find(
                {"key": {"$in": list(provider_keys)}},
                {"_id": 0},
            )
            providers_list = await providers_cursor.to_list(length=len(provider_keys))
            provider_map = {p["key"]: p for p in providers_list}
        else:
            provider_map = {}

        for model in models:
            provider = provider_map.get(model.get("provider_key"))
            model["provider_name"] = provider["name"] if provider else None
            model["provider_url"] = provider["url"] if provider else None

    return models