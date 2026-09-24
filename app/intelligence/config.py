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


def get_hourly_rate(contract_type: str = "project_fixed") -> int:
    """Tarifa horaria (USD) segun el tipo de contrato.

    Fuente unica para ambas tarifas, leidas de entorno con fallback 18:

      - ``project_fixed``       -> ``HOURLY_RATE_PROJECT_FIXED``      (default 18)
      - ``staff_augmentation``  -> ``HOURLY_RATE_STAFF_AUGMENTATION`` (default 18)

    Cualquier otro valor recae en la tarifa de project_fixed. Reemplaza los
    literales ``default(25)`` de los templates y el hardcodeo previo, de modo
    que la tarifa aplicada siempre venga de la configuracion y no del LLM.
    """
    if contract_type == "staff_augmentation":
        raw = os.environ.get("HOURLY_RATE_STAFF_AUGMENTATION", "18")
    else:
        raw = os.environ.get("HOURLY_RATE_PROJECT_FIXED", "18")
    try:
        value = int(str(raw).strip())
    except (ValueError, AttributeError):
        logger.warning(
            f"Tarifa horaria invalida {raw!r} para contract_type={contract_type!r}; "
            "usando 18 por defecto."
        )
        value = 18
    return value