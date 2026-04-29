import os
from loguru import logger
from dotenv import load_dotenv
from bots.telegram import build_telegram_application

# Carga de variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = os.getenv('MY_TELEGRAM_ID')

logger.add("logs/bot.log", rotation="10 MB", retention="10 days", level="INFO")

if __name__ == '__main__':
    if not TOKEN or not ADMIN_ID:
        logger.error("Faltan variables críticas en el archivo .env (TOKEN o ADMIN_ID)")
    else:
        logger.info("Iniciando Bot en modo Polling...")
        application = build_telegram_application(TOKEN)
        application.run_polling()