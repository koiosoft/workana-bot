import time

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from app.config.database import get_mongo_config

MAX_RETRIES = 3
BASE_DELAY = 2  # segundos (backoff: 2s, 4s, 8s)

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
    
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            delay = BASE_DELAY ** attempt  # 2, 4, 8 segundos
            if attempt > 1:
                print(f"🔄 Reintento {attempt}/{MAX_RETRIES} en {delay}s...")
                time.sleep(delay)
            else:
                print("🔌 Conectando a MongoDB (Sync Driver)...")

            _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Validar la conexión
            _client.admin.command('ping')
            _db = _client[db_name]
            print("✅ Conexión a MongoDB (Sync Driver) establecida con éxito.")
            return _db
        except ConnectionFailure as e:
            last_error = e
            print(f"❌ Intento {attempt}/{MAX_RETRIES} fallido: {e}")
            _client = None
            _db = None

    # Se agotaron los reintentos
    print(f"❌ No se pudo conectar a MongoDB después de {MAX_RETRIES} intentos.")
    raise last_error

def close_db_connection():
    """Cierra la conexión síncrona a MongoDB."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        print("🔌 Conexión a MongoDB (Sync Driver) cerrada.")
