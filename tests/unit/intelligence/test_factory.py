"""Unit tests for the intelligence service factory (get_intelligence_service)."""

import os
from unittest.mock import patch

import pytest

from app.intelligence import factory
from app.intelligence.adapters.gemini import GeminiAdapter
from app.intelligence.adapters.openrouter import OpenRouterAdapter
from app.intelligence.port import IntelligencePort


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the factory singleton before each test to ensure isolation."""
    factory._instance = None
    yield
    factory._instance = None


@pytest.fixture
def patch_gemini_client() -> None:
    """Prevent GeminiAdapter from attempting real API client construction."""
    with patch("app.intelligence.adapters.gemini.genai.Client"):
        yield


class TestGetIntelligenceService:
    """Tests for get_intelligence_service() factory function."""

    def test_factory_returns_gemini_when_ai_provider_is_gemini(
        self, patch_gemini_client: None
    ) -> None:
        """When AI_PROVIDER=gemini, should return a GeminiAdapter instance."""
        with patch.dict(
            os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "dummy"}
        ):
            service = factory.get_intelligence_service()
            assert isinstance(service, GeminiAdapter)

    def test_factory_returns_openrouter_when_ai_provider_is_openrouter(
        self,
    ) -> None:
        """When AI_PROVIDER=openrouter, should return an OpenRouterAdapter instance."""
        with patch.dict(
            os.environ,
            {"AI_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "dummy"},
        ):
            service = factory.get_intelligence_service()
            assert isinstance(service, OpenRouterAdapter)

    def test_factory_raises_value_error_for_unknown_provider(self) -> None:
        """When AI_PROVIDER is unknown, should raise ValueError."""
        with patch.dict(os.environ, {"AI_PROVIDER": "unknown"}):
            with pytest.raises(ValueError, match="Proveedor de IA desconocido"):
                factory.get_intelligence_service()

    def test_factory_is_singleton(self, patch_gemini_client: None) -> None:
        """Two consecutive calls should return the exact same object."""
        with patch.dict(
            os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "dummy"}
        ):
            first = factory.get_intelligence_service()
            second = factory.get_intelligence_service()
            assert first is second

    def test_factory_respects_default_provider(self, patch_gemini_client: None) -> None:
        """Without AI_PROVIDER set, should default to GeminiAdapter."""
        # Remove AI_PROVIDER from env to test default behaviour
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "dummy"},
            clear=True,
        ):
            service = factory.get_intelligence_service()
            assert isinstance(service, GeminiAdapter)
