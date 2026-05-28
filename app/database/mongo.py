import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger

from app.config.database import get_mongo_config


_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo(application):
    """Inicializa la conexión a MongoDB y la asigna a una variable global."""
    global _client, _db
    if _db is not None:
        logger.info("La conexión a MongoDB ya existe.")
        return

    uri, db_name = get_mongo_config()
    
    logger.info("🔌 Conectando a MongoDB...")
    _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    
    try:
        # Validar la conexión
        await _client.server_info()
        _db = _client[db_name]
        logger.success("✅ Conexión a MongoDB establecida con éxito.")
    except Exception as e:
        logger.error(f"❌ No se pudo conectar a MongoDB: {e}")
        _client = None
        _db = None
        raise


def get_database() -> AsyncIOMotorDatabase:
    """
    Retorna la instancia de la base de datos.
    Lanza una excepción si la conexión no ha sido inicializada.
    """
    if _db is None:
        raise RuntimeError("La base de datos no ha sido inicializada. Llama a 'connect_to_mongo' primero.")
    return _db


async def close_mongo_connection(application):
    """Cierra la conexión a MongoDB."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("🔌 Conexión a MongoDB cerrada.")
