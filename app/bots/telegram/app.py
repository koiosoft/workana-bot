from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.database.mongo import connect_to_mongo, close_mongo_connection
from .handlers import start, status, fetch_projects, process_projects, unlock_semaphore


async def setup_bot_commands(application):
    """Registra los comandos en el menú azul de Telegram"""
    commands = [
        ("start", "Reiniciar/Ver teclado"),
        ("status", "Ver resumen de cuenta"),
        ("lista", "Buscar proyectos en Workana"),
        ("procesar", "Evaluar proyectos con Gemini"),
        ("desbloquear", "Liberar semáforo (Admin)")
    ]
    await application.bot.set_my_commands(commands)

def build_telegram_application(token: str):
    application = (
        ApplicationBuilder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(30)
        .post_init(setup_bot_commands)
        .post_init(connect_to_mongo)
        .post_shutdown(close_mongo_connection)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("lista", fetch_projects))
    application.add_handler(CommandHandler("procesar", process_projects))
    application.add_handler(CommandHandler("desbloquear", unlock_semaphore))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), start))
    return application
