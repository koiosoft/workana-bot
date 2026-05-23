import os
import sys
from pathlib import Path

# --- Inicio de la corrección de rutas ---
# Añade la raíz del proyecto a sys.path para permitir importaciones absolutas consistentes
# (ej. 'from app.database import ...') tanto en local como en Docker.
# La raíz del proyecto es el directorio padre del directorio 'app' donde está main.py.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
# --- Fin de la corrección de rutas ---

import time
from loguru import logger
from dotenv import load_dotenv
from telegram.error import TimedOut
from bots.telegram import build_telegram_application

# Carga de variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = os.getenv('MY_TELEGRAM_ID')

logger.add("logs/bot.log", rotation="10 MB", retention="10 days", level="INFO")

if __name__ == '__main__':
    if not TOKEN or not ADMIN_ID:
        logger.error("Faltan variables críticas en el archivo .env (TOKEN o ADMIN_ID)")
        sys.exit(1)

    while True:
        try:
            logger.info("Iniciando Bot en modo Polling...")
            application = build_telegram_application(TOKEN)
            application.run_polling()
        except TimedOut:
            logger.warning(
                "Error de Conexión: No se pudo conectar a la API de Telegram (TimedOut). "
                "Reintentando en 30 segundos..."
            )
            time.sleep(30)
        except Exception as e:
            logger.critical(f"Ocurrió un error inesperado y fatal al iniciar el bot: {e}", exc_info=True)
            sys.exit(1)