from pydantic import BaseModel, Field, ConfigDict


class ProviderModel(BaseModel):
    """Pydantic model for an AI model provider."""

    model_config = ConfigDict(populate_by_name=True)

    key: str = Field(..., min_length=1, description="Unique provider key (e.g., 'openrouter', 'gemini')")
    name: str = Field(..., min_length=1, description="Human-readable provider name")
    url: str = Field(..., min_length=1, description="Provider's base URL")