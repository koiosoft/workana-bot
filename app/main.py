import os
import asyncio
from loguru import logger
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Configuración de Logs
logger.add("logs/bot.log", rotation="10 MB", retention="10 days", level="INFO")

# Carga de variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = os.getenv('MY_TELEGRAM_ID')

# Middleware de Seguridad
async def is_admin(update: Update) -> bool:
    user_id = str(update.effective_user.id) if update.effective_user else None
    if user_id == str(ADMIN_ID):
        return True
    logger.warning(f"Intento de acceso no autorizado: ID {user_id}")
    return False

# Handlers de Comandos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        if update.message:
            await update.message.reply_text("⛔ Acceso denegado.")
            return
        else:
            logger.info("No es valido el comando...")

    # Teclado principal para acceso rápido
    keyboard = [['/status', '/lista'], ['/ayuda']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    logger.info(f"Admin {ADMIN_ID} ha iniciado el bot.")
    if update.message:
        await update.message.reply_text(
            "🚀 **Command Center Workana Online**\n"
            "Esperando detección de proyectos...",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        logger.info("No es valido el comando...")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return  # noqa: E701
    if update.message:
        await update.message.reply_text("📊 **Resumen actual:**\n- Propuestas activas: 0\n- En negociación: 0\n- Connects: 50", parse_mode='Markdown')
    else:
        logger.info("No es valido el comando...")

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update): return  # noqa: E701
    if update.message:    
        await update.message.reply_text("📂 No hay proyectos analizados pendientes de aprobación.")
    else:
        logger.info("No es valido el comando...")

if __name__ == '__main__':
    if not TOKEN or not ADMIN_ID:
        logger.error("Faltan variables críticas en el archivo .env (TOKEN o ADMIN_ID)")
    else:
        logger.info("Iniciando Bot en modo Polling...")
        
        application = ApplicationBuilder().token(TOKEN).build()
        
        # Registro de comandos
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('status', status))
        application.add_handler(CommandHandler('lista', lista))
        
        # Handler para mensajes de texto (opcional)
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), start))

        application.run_polling()