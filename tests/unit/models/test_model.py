"""Unit tests for ModelModel Pydantic validation rules.

Coverage:
  - Valid model creation (default standard, default premium, non-default)
  - Required-field validation
  - Format / length constraints
  - Type coercion and rejection
  - Cross-document constraints are documented as repository-level concerns
"""

import pytest
from pydantic import ValidationError
from app.models.model import ModelModel


class TestModelModelValidCreation:
    """Tests for valid ModelModel instances."""

    def test_create_default_standard_model(self) -> None:
        """A default non-premium (standard) model should be valid."""
        model = ModelModel(
            model_id="qwen/qwen3-14b",
            provider_key="openrouter",
            is_default=True,
            is_premium=False,
        )
        assert model.model_id == "qwen/qwen3-14b"
        assert model.provider_key == "openrouter"
        assert model.is_default is True
        assert model.is_premium is False

    def test_create_default_premium_model(self) -> None:
        """A default premium model should be valid."""
        model = ModelModel(
            model_id="deepseek/deepseek-v4-pro",
            provider_key="openrouter",
            is_default=True,
            is_premium=True,
        )
        assert model.is_default is True
        assert model.is_premium is True

    def test_create_non_default_model(self) -> None:
        """A non-default model should be valid."""
        model = ModelModel(
            model_id="models/gemini-2.5-flash",
            provider_key="gemini",
            is_default=False,
            is_premium=False,
        )
        assert model.is_default is False
        assert model.is_premium is False

    def test_create_non_default_premium_model(self) -> None:
        """A premium model that is NOT default should also be valid."""
        model = ModelModel(
            model_id="models/gemini-2.5-pro",
            provider_key="gemini",
            is_default=False,
            is_premium=True,
        )
        assert model.is_default is False
        assert model.is_premium is True


class TestModelModelRequiredFields:
    """Tests for required-field validation."""

    def test_missing_model_id_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel(
                provider_key="openrouter",
                is_default=True,
                is_premium=False,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("model_id",) for e in errors)

    def test_missing_provider_key_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel(
                model_id="gpt-4o",
                is_default=True,
                is_premium=False,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("provider_key",) for e in errors)

    def test_missing_is_default_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel(
                model_id="gpt-4o",
                provider_key="openrouter",
                is_premium=False,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("is_default",) for e in errors)

    def test_missing_is_premium_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel(
                model_id="gpt-4o",
                provider_key="openrouter",
                is_default=True,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("is_premium",) for e in errors)

    def test_missing_all_fields_raises_multiple_errors(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel()  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        locs = {e["loc"] for e in errors}
        assert ("model_id",) in locs
        assert ("provider_key",) in locs
        assert ("is_default",) in locs
        assert ("is_premium",) in locs


class TestModelModelFormatConstraints:
    """Tests for length and type constraints."""

    def test_empty_model_id_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel(
                model_id="",
                provider_key="openrouter",
                is_default=True,
                is_premium=False,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("model_id",) for e in errors)

    def test_empty_provider_key_raises_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ModelModel(
                model_id="gpt-4o",
                provider_key="",
                is_default=True,
                is_premium=False,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("provider_key",) for e in errors)

    def test_is_default_rejects_non_coercible_string(self) -> None:
        """Passing a non-coercible string for is_default should fail."""
        with pytest.raises(ValidationError):
            ModelModel(
                model_id="gpt-4o",
                provider_key="openrouter",
                is_default="not-a-bool",  # type: ignore[arg-type]
                is_premium=False,
            )

    def test_is_premium_rejects_non_coercible_string(self) -> None:
        """Passing a non-coercible string for is_premium should fail."""
        with pytest.raises(ValidationError):
            ModelModel(
                model_id="gpt-4o",
                provider_key="openrouter",
                is_default=True,
                is_premium="invalid",  # type: ignore[arg-type]
            )

    def test_is_default_coerces_int_0_to_false(self) -> None:
        """Pydantic coerces int 0 to False for bool fields."""
        model = ModelModel(
            model_id="gpt-4o",
            provider_key="openrouter",
            is_default=0,  # type: ignore[arg-type]
            is_premium=0,  # type: ignore[arg-type]
        )
        assert model.is_default is False
        assert model.is_premium is False

    def test_is_default_coerces_int_1_to_true(self) -> None:
        """Pydantic coerces int 1 to True for bool fields."""
        model = ModelModel(
            model_id="gpt-4o",
            provider_key="openrouter",
            is_default=1,  # type: ignore[arg-type]
            is_premium=1,  # type: ignore[arg-type]
        )
        assert model.is_default is True
        assert model.is_premium is True

    def test_is_default_coerces_truthy_string(self) -> None:
        """Pydantic coerces 'true'/'false' strings to bool."""
        model = ModelModel(
            model_id="gpt-4o",
            provider_key="openrouter",
            is_default="true",  # type: ignore[arg-type]
            is_premium="false",  # type: ignore[arg-type]
        )
        assert model.is_default is True
        assert model.is_premium is False


class TestModelModelCrossDocumentConstraints:
    """Document the cross-document constraints enforced at the repository level.

    These constraints cannot be validated by Pydantic on a single instance:
      - No more than 2 models may have is_default=True across the collection.
      - Exactly 1 default premium model (is_default=True, is_premium=True).
      - Exactly 1 default standard model (is_default=True, is_premium=False).

    The Pydantic model alone allows any valid combination; these rules are
    enforced in the ModelsRepository when inserting or updating documents.
    """

    def test_two_models_can_both_be_default_at_instance_level(self) -> None:
        """Pydantic does not prevent two instances from both having is_default=True."""
        model_a = ModelModel(
            model_id="model-a",
            provider_key="prov",
            is_default=True,
            is_premium=False,
        )
        model_b = ModelModel(
            model_id="model-b",
            provider_key="prov",
            is_default=True,
            is_premium=True,
        )
        assert model_a.is_default is True
        assert model_b.is_default is True

    def test_model_can_be_default_and_premium(self) -> None:
        """A single model can be both default and premium (valid at instance level)."""
        model = ModelModel(
            model_id="premium-default",
            provider_key="prov",
            is_default=True,
            is_premium=True,
        )
        assert model.is_default is True
        assert model.is_premium is True