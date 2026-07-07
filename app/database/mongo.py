from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from app.config.database import get_mongo_config

_db: Optional[AsyncIOMotorDatabase] = None

def get_database() -> AsyncIOMotorDatabase:
    """
    Retorna la instancia de la base de datos.
    Inicializa la conexión si no ha sido creada previamente.
    """
    global _db
    if _db is None:
        mongo_uri, db_name = get_mongo_config()
        client = AsyncIOMotorClient(mongo_uri)
        _db = client[db_name]
    return _db

async def connect_to_mongo(*args, **kwargs) -> AsyncIOMotorDatabase:
    global _db
    mongo_uri, db_name = get_mongo_config()
    client = AsyncIOMotorClient(mongo_uri)
    _db = client[db_name]
    return _db

async def close_mongo_connection(*args, **kwargs):
    global _db
    if _db is not None:
        _db.client.close()
        _db = None


async def ensure_providers_collection() -> str:
    """
    Ensure the 'providers' collection exists with schema validation.
    Fields: key (string, required), name (string, required), url (string, required).
    Returns the collection name on success.
    """
    db = get_database()
    collections = await db.list_collection_names()
    if "providers" not in collections:
        await db.create_collection(
            "providers",
            validator={
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["key", "name", "url"],
                    "properties": {
                        "key": {
                            "bsonType": "string",
                            "description": "Unique provider key (e.g., 'openrouter', 'gemini')"
                        },
                        "name": {
                            "bsonType": "string",
                            "description": "Human-readable provider name"
                        },
                        "url": {
                            "bsonType": "string",
                            "description": "Provider's base URL"
                        }
                    }
                }
            }
        )
    # Create a unique index on the key field (always ensure it exists)
    await db["providers"].create_index("key", unique=True)
    return "providers"


async def ensure_models_collection() -> str:
    """
    Ensure the 'models' collection exists with schema validation.
    Fields: model_id (string, required), provider_key (string, required),
    is_default (boolean, required), is_premium (boolean, required).

    Collection-level constraints (enforced at repository level):
    - No more than 2 default models total
    - Exactly 1 default premium model and exactly 1 default standard model
    """
    db = get_database()
    collections = await db.list_collection_names()
    if "models" not in collections:
        await db.create_collection(
            "models",
            validator={
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["model_id", "provider_key", "is_default", "is_premium"],
                    "properties": {
                        "model_id": {
                            "bsonType": "string",
                            "minLength": 1,
                            "description": "Unique model identifier (e.g., 'gpt-4o', 'gemini-2.5-flash')"
                        },
                        "provider_key": {
                            "bsonType": "string",
                            "minLength": 1,
                            "description": "Foreign key referencing ProviderModel.key"
                        },
                        "is_default": {
                            "bsonType": "bool",
                            "description": "Whether this model is a default selection for its tier"
                        },
                        "is_premium": {
                            "bsonType": "bool",
                            "description": "Whether this model belongs to the premium tier"
                        }
                    }
                }
            }
        )
    # Create a unique compound index on model_id + provider_key (always ensure it exists)
    await db["models"].create_index([("model_id", 1), ("provider_key", 1)], unique=True)
    return "models"
