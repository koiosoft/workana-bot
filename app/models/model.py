from pydantic import BaseModel, Field, ConfigDict, model_validator


class ModelModel(BaseModel):
    """Pydantic model representing an AI model entry in the models collection.

    Validation rules:
    - model_id: required, non-empty string
    - provider_key: required, non-empty string
    - is_default: required boolean
    - is_premium: required boolean
    - At most 2 models can be marked as default across the collection
    - Exactly 1 default premium model and exactly 1 default standard model
      (enforced at the repository level when inserting/updating)
    """

    model_config = ConfigDict(populate_by_name=True)

    model_id: str = Field(..., min_length=1, description="Unique model identifier (e.g., 'gpt-4o', 'gemini-2.5-flash')")
    provider_key: str = Field(..., min_length=1, description="Foreign key referencing ProviderModel.key")
    is_default: bool = Field(..., description="Whether this model is a default selection for its tier")
    is_premium: bool = Field(..., description="Whether this model belongs to the premium tier")

    @model_validator(mode="after")
    def validate_category_consistency(self) -> "ModelModel":
        """Ensure is_default and is_premium are boolean values."""
        if not isinstance(self.is_default, bool):
            raise ValueError("is_default must be a boolean value")
        if not isinstance(self.is_premium, bool):
            raise ValueError("is_premium must be a boolean value")
        return self