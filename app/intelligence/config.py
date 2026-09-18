"""
Configuration module for the intelligence staged pipeline.

Provides ``get_maturity_threshold()`` as the **single source** for the
maturity threshold used in the ``project_fixed`` staged pipeline.  Threshold is
read from the ``MATURITY_THRESHOLD`` environment variable with a default of 8.

Decision #10: MATURITY_THRESHOLD se configura por variable de entorno (default 8).
"""

import os

from loguru import logger


def get_maturity_threshold() -> int:
    """Read and parse ``MATURITY_THRESHOLD`` from the environment.

    Returns:
        The maturity threshold as an integer.

    Raises:
        ValueError: If the environment variable is present but is not a valid
            integer.  This is a strict parse — no silent fallback to the
            default when parsing fails.
    """
    raw = os.environ.get("MATURITY_THRESHOLD", "8")

    try:
        value = int(raw.strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            f"MATURITY_THRESHOLD must be a valid integer, got {raw!r}. "
            "Set a proper integer value (e.g. '8') or unset the variable "
            "to use the default."
        ) from exc

    logger.debug(f"Maturity threshold resolved to {value} (from MATURITY_THRESHOLD={raw!r})")
    return value