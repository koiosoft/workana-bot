"""Unit tests for get_maturity_threshold (UNIT021).

Covers:
  - Default value is 8 when MATURITY_THRESHOLD is not set
  - Reads integer from MATURITY_THRESHOLD env var
  - Raises ValueError on non-integer value
  - Raises ValueError on empty string
  - Accepts valid integer strings (positive, zero, negative)
"""

import os
from unittest.mock import patch

import pytest

from app.intelligence.config import get_maturity_threshold


class TestGetMaturityThreshold:
    """Validate the single source of the maturity threshold config."""

    def test_default_is_eight(self) -> None:
        """When MATURITY_THRESHOLD is unset, default should be 8."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_maturity_threshold() == 8

    def test_reads_integer_from_env(self) -> None:
        """Should parse a valid integer string from the environment."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "5"}):
            assert get_maturity_threshold() == 5

    def test_accepts_zero(self) -> None:
        """Zero is a valid integer threshold (allowed by the model)."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "0"}):
            assert get_maturity_threshold() == 0

    def test_accepts_negative(self) -> None:
        """Negative is technically a valid integer parse (even if nonsensical)."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "-3"}):
            assert get_maturity_threshold() == -3

    def test_accepts_large_number(self) -> None:
        """Large integers should parse without overflow."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "100"}):
            assert get_maturity_threshold() == 100

    def test_strips_whitespace(self) -> None:
        """Whitespace around the value should be tolerated."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "  7  "}):
            assert get_maturity_threshold() == 7

    def test_raises_on_non_integer_string(self) -> None:
        """ValueError should be raised for non-integer values."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "abc"}):
            with pytest.raises(ValueError, match="MATURITY_THRESHOLD"):
                get_maturity_threshold()

    def test_raises_on_float_string(self) -> None:
        """Float strings are not valid integers."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "8.5"}):
            with pytest.raises(ValueError, match="MATURITY_THRESHOLD"):
                get_maturity_threshold()

    def test_raises_on_empty_string(self) -> None:
        """Empty string should raise ValueError (int('') fails)."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": ""}):
            with pytest.raises(ValueError, match="MATURITY_THRESHOLD"):
                get_maturity_threshold()

    def test_env_takes_precedence_over_default(self) -> None:
        """When set, env var should override the default of 8."""
        with patch.dict(os.environ, {"MATURITY_THRESHOLD": "3"}):
            result = get_maturity_threshold()
            assert result == 3
            assert result != 8