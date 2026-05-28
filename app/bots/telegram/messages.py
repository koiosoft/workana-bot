import asyncio
from telegram import Update
from loguru import logger

TELEGRAM_MAX_MESSAGE = 4000
MAX_RETRIES = 3

async def _send_with_retry(update: Update, text: str):
    """Función de ayuda para enviar un mensaje con reintentos exponenciales."""
    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_text(text)
            return True # Éxito
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                sleep_time = 2 ** (attempt + 1) # 2s, 4s
                logger.warning(f"Error enviando mensaje a Telegram ({e}). Reintentando en {sleep_time}s... (Intento {attempt + 1}/{MAX_RETRIES})")
                await asyncio.sleep(sleep_time)
            else:
                logger.error(f"Fallo definitivo al enviar mensaje a Telegram tras {MAX_RETRIES} intentos: {e}")
                return False

async def send_long_message(update: Update, text: str):
    if not update.message:
        return

    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > TELEGRAM_MAX_MESSAGE:
            await _send_with_retry(update, current)
            current = line
        else:
            current += line

    if current:
        await _send_with_retry(update, current)
