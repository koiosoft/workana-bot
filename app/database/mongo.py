from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import os

_db: Optional[AsyncIOMotorDatabase] = None

def get_database() -> AsyncIOMotorDatabase:
    """
    Retorna la instancia de la base de datos.
    Lanza una excepción si la conexión no ha sido inicializada.
    """
    if _db is None:
        raise RuntimeError("La base de datos no ha sido inicializada. Llama a 'connect_to_mongo' primero.")
    return _db

async def connect_to_mongo(*args, **kwargs) -> AsyncIOMotorDatabase:
    global _db
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "workana_bot")
    client = AsyncIOMotorClient(mongo_uri)
    _db = client[db_name]
    return _db

async def close_mongo_connection(*args, **kwargs):
    global _db
    if _db is not None:
        _db.client.close()
        _db = None
