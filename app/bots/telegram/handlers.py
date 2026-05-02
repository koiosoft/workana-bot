import os
import asyncio
from loguru import logger
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from scraper.factory import ScraperFactory
from database import get_projects_repository
from intelligence.factory import get_intelligence_service
from .messages import send_long_message


async def is_admin(update: Update) -> bool:
    admin_id = os.getenv("MY_TELEGRAM_ID")
    user_id = str(update.effective_user.id) if update.effective_user else None
    if user_id == str(admin_id):
        return True
    logger.warning(f"Intento de acceso no autorizado: ID {user_id}")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        if update.message:
            await update.message.reply_text("⛔ Acceso denegado.")
        return

    keyboard = [["/status", "/lista"], ["/procesar", "/ayuda"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    logger.info(f"Admin {os.getenv('MY_TELEGRAM_ID')} ha iniciado el bot." )
    if update.message:
        await update.message.reply_text(
            "🚀 **Command Center Workana Online**\n"
            "Esperando detección de proyectos...",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    if update.message:
        await update.message.reply_text(
            "📊 **Resumen actual:**\n- Propuestas activas: 0\n- En negociación: 0\n- Connects: 50",
            parse_mode="Markdown",
        )


async def fetch_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    if not update.message:
        return

    projects_repository = get_projects_repository()
    await update.message.reply_text("🔍 Consultando nuevos proyectos...")
    
    scraper = ScraperFactory.get_scraper()
    projects = await scraper.get_projects()
    logger.info(f"Se obtuvieron {len(projects)} proyectos del scraping.")

    if not projects:
        await update.message.reply_text("📭 No se encontraron proyectos nuevos.")
        return

    save_stats = await projects_repository.save_scraped_projects(projects)
    await update.message.reply_text(
        "💾 Guardado en MongoDB:\n"
        f"- Nuevos: {save_stats['inserted']}\n"
        f"- Ya existentes: {save_stats['existing']}"
    )

    msg = "✅ Proyectos detectados:\n\n"
    for p in projects:
        msg += f"🔹 {p['title']} - {p['budget']}\n"
    await send_long_message(update, msg)


async def process_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    if not update.message:
        return

    await update.message.reply_text("🧠 Obteniendo proyectos pendientes para evaluación con IA...")
    
    projects_repository = get_projects_repository()
    ai_service = get_intelligence_service()

    # Limitamos a 5 para pruebas y evitar agotar la cuota de la API
    projects = await projects_repository.claim_pending_projects(limit=5)
    if not projects:
        await update.message.reply_text("📭 No hay proyectos pendientes en la base de datos.")
        return

    await update.message.reply_text(f"🤖 Evaluando {len(projects)} proyectos con Gemini. Esto puede tardar un momento...")

    # Ejecutamos las evaluaciones de IA en paralelo
    evaluation_tasks = [ai_service.evaluate_project(p) for p in projects]
    evaluations = await asyncio.gather(*evaluation_tasks)

    proposed_hashes: list[str] = []
    ignored_hashes: list[str] = []
    ai_summary: list[str] = []

    for project, evaluation in zip(projects, evaluations):
        link_hash = project.get("link_hash")
        if not link_hash:
            continue

        should_propose = evaluation.get("should_propose", False)
        reason = evaluation.get("reason", "Sin razón especificada.")
        
        title = project.get('title', 'N/A')
        decision_emoji = "✅" if should_propose else "❌"
        ai_summary.append(f"{decision_emoji} *{title}*: {reason}")

        if should_propose:
            proposed_hashes.append(link_hash)
            logger.success(f"IA decidió PROPONER para '{title}'. Razón: {reason}")
        else:
            ignored_hashes.append(link_hash)
            logger.warning(f"IA decidió IGNORAR para '{title}'. Razón: {reason}")

    # Actualizamos el estado en la base de datos
    proposed_count = await projects_repository.mark_projects_status(proposed_hashes, "proposed_by_ai")
    ignored_count = await projects_repository.mark_projects_status(ignored_hashes, "ignored_by_ai")

    # Enviamos el resumen al usuario
    summary_msg = (
        "🧠 **Procesamiento con IA completado:**\n\n"
        f"- Proyectos evaluados: {len(projects)}\n"
        f"- Propuestas recomendadas: {proposed_count}\n"
        f"- Ignorados: {ignored_count}\n\n"
        "**Resumen de decisiones:**\n"
    )
    summary_msg += "\n\n".join(ai_summary)

    await send_long_message(update, summary_msg )