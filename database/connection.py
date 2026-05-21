from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from app.config.database import get_mongo_config

_client: MongoClient | None = None
_db: Database | None = None

def get_db_connection() -> Database:
    """
    Establece y devuelve una conexión síncrona a la base de datos MongoDB,
    utilizando la configuración centralizada.
    """
    global _client, _db
    if _db is not None:
        return _db

    uri, db_name = get_mongo_config()
    
    print("🔌 Conectando a MongoDB (Sync Driver)...")
    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    
    try:
        # Validar la conexión
        _client.admin.command('ping')
        _db = _client[db_name]
        print("✅ Conexión a MongoDB (Sync Driver) establecida con éxito.")
        return _db
    except ConnectionFailure as e:
        print(f"❌ No se pudo conectar a MongoDB (Sync Driver): {e}")
        _client = None
        _db = None
        raise

def close_db_connection():
    """Cierra la conexión síncrona a MongoDB."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        print("🔌 Conexión a MongoDB (Sync Driver) cerrada.")
