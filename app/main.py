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
from telegram.error import TimedOut, TelegramError, NetworkError
from app.bots.telegram.app import build_telegram_application

# Carga de variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = os.getenv('MY_TELEGRAM_ID')

logger.add("logs/bot.log", rotation="10 MB", retention="10 days", level="INFO")

if __name__ == '__main__':
    if not TOKEN or not ADMIN_ID:
        logger.error("Faltan variables críticas en el archivo .env (TOKEN o ADMIN_ID)")
        sys.exit(1)

    # Configuración de reintentos:
    # 3 intentos rápidos fijos (300ms), luego backoff exponencial (×2)
    BACKOFF_BASE = 0.3  # 300ms
    MAX_FAST_RETRIES = 3
    MAX_DELAY = 120  # 120 segundos máximo

    fail_count = 0

    while True:
        try:
            logger.info("Iniciando Bot en modo Polling...")
            application = build_telegram_application(TOKEN)
            # Ignorar mensajes viejos que puedan estar bloqueando el inicio
            application.run_polling(drop_pending_updates=True)
        except (TimedOut, TelegramError) as e:
            fail_count += 1
            if fail_count <= MAX_FAST_RETRIES:
                delay = BACKOFF_BASE
                mode = "rápido"
            else:
                backoff_power = (fail_count - MAX_FAST_RETRIES)
                delay = min(BACKOFF_BASE * (2 ** backoff_power), MAX_DELAY)
                mode = "exponencial"

            logger.warning(
                f"Error de conexión con Telegram: {e}. "
                f"Reintentando en {delay}s (fallo #{fail_count}, modo {mode})..."
            )
            time.sleep(delay)
        except NetworkError as e:
            fail_count += 1
            delay = min(BACKOFF_BASE * (2 ** max(0, fail_count - MAX_FAST_RETRIES)), MAX_DELAY)
            logger.warning(
                f"Error de red con Telegram: {e}. "
                f"Reintentando en {delay}s (fallo #{fail_count})..."
            )
            time.sleep(delay)
        except Exception as e:
            logger.critical(f"Ocurrió un error inesperado y fatal: {e}", exc_info=True)
            sys.exit(1)
