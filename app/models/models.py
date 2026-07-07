"""Pydantic models for Model Providers and Models (LLMs).

Defines the canonical schemas used by the ModelsRouter endpoints:
  - ModelProvider : represents an AI model provider
  - Model         : represents an LLM entry linked to a provider
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelProvider(BaseModel):
    """Pydantic model representing an AI model provider.

    Fields:
        id: MongoDB ObjectId (aliased from _id).
        name: Human-readable provider name.
        description: Optional provider description.
        created_at: Timestamp of creation (UTC).
        updated_at: Timestamp of last update (UTC).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId")
    name: str = Field(..., min_length=1, description="Human-readable provider name")
    description: Optional[str] = Field(None, description="Provider description")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp (UTC)")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp (UTC)")


class Model(BaseModel):
    """Pydantic model representing an LLM entry.

    Fields:
        id: MongoDB ObjectId (aliased from _id).
        provider_id: Foreign key referencing the parent ModelProvider.id.
        model_id: Provider-specific model identifier (e.g. ``'models/gemini-2.5-flash'``).
        name: Human-readable model name (e.g., 'GPT-4o').
        is_default: Whether this model is the default for its tier.
        is_premium: Whether this model belongs to the premium tier.
        model_type: Optional tier hint for disambiguation
            (``"standard"``, ``"premium"``, or ``"filter"``).
            Filter models are non-transactional and excluded from
            ``is_premium`` checks.
        created_at: Timestamp of creation (UTC).
        updated_at: Timestamp of last update (UTC).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId")
    provider_id: str = Field(..., min_length=1, description="Foreign key referencing ModelProvider.id")
    model_id: str = Field(..., min_length=1, description="Provider-specific model identifier (e.g. 'models/gemini-2.5-flash')")
    name: str = Field(..., min_length=1, description="Human-readable model name")
    is_default: bool = Field(False, description="Whether this model is a default selection for its tier")
    is_premium: bool = Field(False, description="Whether this model belongs to the premium tier")
    model_type: Optional[str] = Field(None, description="Optional tier hint: 'standard', 'premium', or 'filter'. Filter models are non-transactional.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp (UTC)")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp (UTC)")