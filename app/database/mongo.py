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
