"""Migracion: Inserta los modelos de IA iniciales en la coleccion 'models'.

Reglas de negocio:
  - Exactamente 1 modelo estandar por defecto (OpenRouter: qwen/qwen3-14b)
  - Exactamente 1 modelo premium por defecto (OpenRouter: deepseek/deepseek-v4-pro)
  - Los modelos de Gemini se registran como no-default para uso manual.
"""

from pymongo.database import Database
from migrations.core.base import IMigrationContext, MigrationBase

TARGET_COLLECTION = "models"
PROVIDERS_COLLECTION = "providers"

# Providers
PROVIDER_OPENROUTER = {
    "key": "openrouter",
    "name": "OpenRouter",
    "url": "https://openrouter.ai/api/v1",
}
PROVIDER_GEMINI = {
    "key": "gemini",
    "name": "Google Gemini",
    "url": "https://generativelanguage.googleapis.com",
}

# OpenRouter models (set as defaults)
MODEL_OPENROUTER_STANDARD = {
    "model_id": "qwen/qwen3-14b",
    "provider_key": "openrouter",
    "is_default": True,
    "is_premium": False,
}
MODEL_OPENROUTER_PREMIUM = {
    "model_id": "deepseek/deepseek-v4-pro",
    "provider_key": "openrouter",
    "is_default": True,
    "is_premium": True,
}

# Gemini models (non-default)
MODEL_GEMINI_STANDARD = {
    "model_id": "models/gemini-2.5-flash",
    "provider_key": "gemini",
    "is_default": False,
    "is_premium": False,
}
MODEL_GEMINI_PREMIUM = {
    "model_id": "models/gemini-2.5-pro",
    "provider_key": "gemini",
    "is_default": False,
    "is_premium": True,
}


class Migration(MigrationBase):
    """
    Inserta los modelos de IA de OpenRouter y Gemini en la coleccion 'models'.

    OpenRouter actua como proveedor por defecto:
      - qwen/qwen3-14b  -> estandar por defecto  (is_default=true, is_premium=false)
      - deepseek/deepseek-v4-pro -> premium por defecto (is_default=true, is_premium=true)

    Gemini queda registrado como alternativa no predeterminada.
    """

    def up(self, writer: IMigrationContext) -> None:
        # Insert providers first (referenced by models.provider_key)
        writer.add_insert(PROVIDERS_COLLECTION, PROVIDER_OPENROUTER)
        writer.add_insert(PROVIDERS_COLLECTION, PROVIDER_GEMINI)

        # Insert models
        writer.add_insert(TARGET_COLLECTION, MODEL_OPENROUTER_STANDARD)
        writer.add_insert(TARGET_COLLECTION, MODEL_OPENROUTER_PREMIUM)
        writer.add_insert(TARGET_COLLECTION, MODEL_GEMINI_STANDARD)
        writer.add_insert(TARGET_COLLECTION, MODEL_GEMINI_PREMIUM)

    def down(self, db: Database) -> None:
        """Elimina los documentos insertados por esta migracion."""
        model_ids = [
            MODEL_OPENROUTER_STANDARD["model_id"],
            MODEL_OPENROUTER_PREMIUM["model_id"],
            MODEL_GEMINI_STANDARD["model_id"],
            MODEL_GEMINI_PREMIUM["model_id"],
        ]
        db[TARGET_COLLECTION].delete_many(
            {"model_id": {"$in": model_ids}}
        )
        provider_keys = [PROVIDER_OPENROUTER["key"], PROVIDER_GEMINI["key"]]
        db[PROVIDERS_COLLECTION].delete_many(
            {"key": {"$in": provider_keys}}
        )