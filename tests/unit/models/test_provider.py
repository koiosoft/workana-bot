"""Unit tests for ProviderModel Pydantic validation rules."""

import pytest
from pydantic import ValidationError
from app.models.provider import ProviderModel


class TestProviderModelValidCreation:
    """Tests for valid ProviderModel instances."""

    def test_create_provider_with_all_fields(self) -> None:
        """Should create a ProviderModel when all required fields are provided."""
        provider = ProviderModel(
            key="openrouter",
            name="OpenRouter",
            url="https://openrouter.ai/api/v1",
        )
        assert provider.key == "openrouter"
        assert provider.name == "OpenRouter"
        assert provider.url == "https://openrouter.ai/api/v1"

    def test_create_provider_minimal_valid_values(self) -> None:
        """Should accept single-character values (min_length=1)."""
        provider = ProviderModel(key="a", name="b", url="c")
        assert provider.key == "a"
        assert provider.name == "b"
        assert provider.url == "c"


class TestProviderModelRequiredFields:
    """Tests for required-field validation."""

    def test_missing_key_raises_error(self) -> None:
        """Should raise ValidationError when 'key' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel(name="OpenRouter", url="https://openrouter.ai/api/v1")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("key",) for e in errors)

    def test_missing_name_raises_error(self) -> None:
        """Should raise ValidationError when 'name' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel(key="openrouter", url="https://openrouter.ai/api/v1")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_missing_url_raises_error(self) -> None:
        """Should raise ValidationError when 'url' is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel(key="openrouter", name="OpenRouter")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("url",) for e in errors)

    def test_missing_all_fields_raises_errors(self) -> None:
        """Should raise ValidationError with multiple errors when all fields are missing."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel()  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        locs = {e["loc"] for e in errors}
        assert ("key",) in locs
        assert ("name",) in locs
        assert ("url",) in locs


class TestProviderModelFormatConstraints:
    """Tests for format/length constraints."""

    def test_empty_key_raises_error(self) -> None:
        """Should reject empty string for 'key' (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel(key="", name="OpenRouter", url="https://openrouter.ai/api/v1")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("key",) for e in errors)

    def test_empty_name_raises_error(self) -> None:
        """Should reject empty string for 'name' (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel(key="openrouter", name="", url="https://openrouter.ai/api/v1")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_empty_url_raises_error(self) -> None:
        """Should reject empty string for 'url' (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderModel(key="openrouter", name="OpenRouter", url="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("url",) for e in errors)

    def test_non_string_key_raises_error(self) -> None:
        """Should reject non-string value for 'key'."""
        with pytest.raises(ValidationError):
            ProviderModel(key=123, name="OpenRouter", url="https://openrouter.ai/api/v1")  # type: ignore[arg-type]

    def test_non_string_name_raises_error(self) -> None:
        """Should reject non-string value for 'name'."""
        with pytest.raises(ValidationError):
            ProviderModel(key="openrouter", name=456, url="https://openrouter.ai/api/v1")  # type: ignore[arg-type]

    def test_non_string_url_raises_error(self) -> None:
        """Should reject non-string value for 'url'."""
        with pytest.raises(ValidationError):
            ProviderModel(key="openrouter", name="OpenRouter", url=True)  # type: ignore[arg-type]

    def test_extra_fields_are_ignored(self) -> None:
        """Should ignore extra fields not defined in the model."""
        provider = ProviderModel(
            key="gemini",
            name="Google Gemini",
            url="https://ai.google.dev",
            extra="should be ignored",  # type: ignore[call-arg]
        )
        assert not hasattr(provider, "extra")