"""Interface compliance tests for IntelligencePort and its adapters."""

import inspect
from typing import get_type_hints

from app.intelligence.adapters.gemini import GeminiAdapter
from app.intelligence.adapters.openrouter import OpenRouterAdapter
from app.intelligence.port import IntelligencePort


class TestInterfaceCompliance:
    """Verify both adapters correctly implement the IntelligencePort contract."""

    def test_gemini_adapter_implements_port(self) -> None:
        """GeminiAdapter must be a subclass of IntelligencePort."""
        assert issubclass(GeminiAdapter, IntelligencePort)

    def test_openrouter_adapter_implements_port(self) -> None:
        """OpenRouterAdapter must be a subclass of IntelligencePort."""
        assert issubclass(OpenRouterAdapter, IntelligencePort)

    def test_port_has_required_abstract_methods(self) -> None:
        """The ABC must define exactly the three required async methods."""
        expected = {
            "evaluate_projects",
            "generate_proposal",
            "format_project_description",
        }
        assert IntelligencePort.__abstractmethods__ == expected

    def test_both_adapters_accept_circuit_breaker_parameter(self) -> None:
        """All three interface methods must accept an optional circuit_breaker parameter."""
        method_names = [
            "evaluate_projects",
            "generate_proposal",
            "format_project_description",
        ]

        for adapter_cls in (GeminiAdapter, OpenRouterAdapter):
            for name in method_names:
                sig = inspect.signature(getattr(adapter_cls, name))
                assert (
                    "circuit_breaker" in sig.parameters
                ), f"{adapter_cls.__name__}.{name}() is missing circuit_breaker parameter"
