import os
from loguru import logger
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from scraper import scraper_service
from database import get_projects_repository
from .messages import send_long_message


async def is_admin(update: Update) -> bool:
    admin_id = os.getenv("MY_TELEGRAM_ID")
    user_id = str(update.effective_user.id) if update.effective_user else None
    if user_id == str(admin_id):
        return True
    logger.warning(f"Intento de acceso no autorizado: ID {user_id}")
    return False


def should_propose(project: dict) -> bool:
    # Regla inicial simple. Luego se reemplaza por evaluación con IA.
    title = (project.get("title") or "").lower()
    blocked_terms = ("wordpress", "shopify", "wix")
    if any(term in title for term in blocked_terms):
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        if update.message:
            await update.message.reply_text("⛔ Acceso denegado.")
        return

    keyboard = [["/status", "/lista"], ["/procesar", "/ayuda"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    logger.info(f"Admin {os.getenv('MY_TELEGRAM_ID')} ha iniciado el bot.")
    if update.message:
        await update.message.reply_text(
            "🚀 **Command Center Workana Online**\n"
            "Esperando detección de proyectos...",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):  # noqa: E701
        return
    if update.message:
        await update.message.reply_text(
            "📊 **Resumen actual:**\n- Propuestas activas: 0\n- En negociación: 0\n- Connects: 50",
            parse_mode="Markdown",
        )


async def fetch_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):  # noqa: E701
        return

    if not update.message:
        return

    projects_repository = get_projects_repository()
    await update.message.reply_text("🔍 Consultando nuevos proyectos...")
    projects = await scraper_service.get_projects()
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
    if not await is_admin(update):  # noqa: E701
        return

    if not update.message:
        return

    projects_repository = get_projects_repository()
    projects = await projects_repository.claim_pending_projects(limit=20)
    if not projects:
        await update.message.reply_text("📭 No hay proyectos pendientes en MongoDB.")
        return

    proposed_hashes: list[str] = []
    ignored_hashes: list[str] = []
    for project in projects:
        link_hash = project.get("link_hash")
        if not link_hash:
            continue
        if should_propose(project):
            proposed_hashes.append(link_hash)
        else:
            ignored_hashes.append(link_hash)

    proposed_count = await projects_repository.mark_projects_status(proposed_hashes, "proposed")
    ignored_count = await projects_repository.mark_projects_status(ignored_hashes, "ignored")

    msg = "🧠 Procesamiento de proyectos completado:\n\n"
    msg += f"- Tomados de pending: {len(projects)}\n"
    msg += f"- Marcados proposed: {proposed_count}\n"
    msg += f"- Marcados ignored: {ignored_count}\n\n"
    msg += "Primeros proyectos evaluados:\n"
    for p in projects[:10]:
        msg += f"🔹 {p['title']} - {p['budget']}\n{p['link']}\n\n"

    await send_long_message(update, msg)
