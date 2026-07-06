"""Models & Providers API Routes.

Endpoints:
  - GET /api/models/providers       : list all providers
  - GET /api/models                 : list models, optionally filtered by tier
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.database.mongo import get_database
from loguru import logger

router = APIRouter(tags=["models"])


@router.get("/providers")
async def list_providers() -> list[dict]:
    """Return all registered AI model providers."""
    db = get_database()
    cursor = db["providers"].find({}, {"_id": 0})
    providers = await cursor.to_list(length=100)
    return providers


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