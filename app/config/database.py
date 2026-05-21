import os
from typing import Tuple
from dotenv import load_dotenv, find_dotenv

# Cargar .env y luego .env.local (si existe, anulará .env)
# find_dotenv buscará el archivo .env en el directorio actual o en los padres.
load_dotenv(find_dotenv())
# Cargar .env.local explícitamente, override=True asegura que sus valores prevalezcan.
load_dotenv(find_dotenv('.env.local'), override=True)

def get_mongo_config() -> Tuple[str, str]:
    """
    Lee la configuración de MongoDB desde las variables de entorno.

    Prioriza MONGO_URI. Si no se encuentra, lanza un error para evitar
    intentar conectar con una configuración inválida.
    """
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError(
            "La variable de entorno MONGO_URI no está definida. "
            "Asegúrate de que tu archivo .env o .env.local la contenga."
        )

    db_name = os.getenv("MONGO_DB_NAME", "workana_bot")
    
    return uri, db_name