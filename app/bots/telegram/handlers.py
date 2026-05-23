import os
import asyncio
import time
from loguru import logger
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from scraper.factory import ScraperFactory
from app.database import get_projects_repository
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

    keyboard = [["/status", "/lista" ],["/procesar"]]
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
        f"💾 **Sincronización DB:**\n"
        f"- Nuevos: {save_stats['inserted']}\n"
        f"- Actualizados/Existentes: {save_stats['existing']}"
    )

    ai_service = get_intelligence_service()
    total_processed = 0
    all_relevant = []
    max_iterations = 10
    buffer_size = 10
    iterations = 0
    await update.message.reply_text("🧠 Se evaluará la cola de proyectos pendientes en 30 segundos")

    time.sleep(30)
    while iterations < max_iterations:
        iterations += 1
        # Recuperamos un lote para no saturar la memoria ni la API de la IA
        batch = await projects_repository.claim_pending_projects(limit=buffer_size)
        
        if not batch:
            logger.info("No hay proyectos pendientes.  Batch dio Null o 0")
            break # Ya no quedan proyectos 'pending'

        try:
            await update.message.reply_text(f"🧠 Iniciando la evaluación del Lote #{iterations} con {buffer_size} proyectos.")
            link_hashes = [p["link_hash"] for p in batch]
            await projects_repository.mark_projects_status(link_hashes, "processing")
            time.sleep(4)
            evaluations =  await ai_service.evaluate_projects(batch)
        except Exception as e:
            logger.critical(f"Abortando: Error de infraestructura en IA: {e}")
            await update.message.reply_text(f"❌ Error crítico: {e}. El proceso se ha detenido para proteger los datos.")
            break

        for project, eval_data in zip(batch, evaluations):
            score = eval_data.get("score", 0)
            strategy = eval_data.get("strategy", "none")
            
            # Actualizamos resultado en DB
            await projects_repository.update_project_analysis(
                project["link_hash"], 
                score=score, 
                reason=eval_data.get("reason", 'Sin razón especificada.'),
                strategy=strategy,
                status="analyzed"
            )

            if score > 4:
                all_relevant.append({**project, **eval_data})

        total_processed += len(batch)
        logger.info(f"Lote de {len(batch)} procesado. Total acumulado: {total_processed}")

    if not all_relevant:
        await update.message.reply_text(f"✅ Se analizaron {total_processed} proyectos. Ninguno superó el Score 6.")
        return

    msg = f"🚀 **{len(all_relevant)} Oportunidades encontradas (de {total_processed} analizados):**\n\n"
    for p in all_relevant:
        msg += (
            f"⭐ **Score: {p['score']}/10**\n"
            f"📌 {p['title']}\n"
            f"💰 {p['budget']}\n"
            f"💡 {p['reason']}\n"
            f"🔗 [Ver Proyecto]({p['link']})\n\n"
        )
    
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
    projects = await projects_repository.get_projects_for_deep_analysis(limit=50)
    if not projects:
        logger.success(f"📭 No hay proyectos pendientes en la base de datos para evaluación inicial.")
        await update.message.reply_text("📭 No hay proyectos pendientes en la base de datos para evaluación inicial.")
        return

    await update.message.reply_text(f"🤖 Evaluando {len(projects)} proyectos con Gemini. Esto puede tardar un momento...")
    scraper = ScraperFactory.get_scraper()

    processed_count = 0
    failed_count = 0

    for project in projects:
        url = project.get('link')
        link_hash = project.get('link_hash')
        title = project.get('title', 'Sin título')
        total_usd = 0

        if not url or not link_hash:
            continue

        try:
            logger.info(f"Extrayendo detalle para: {title}")
            full_detail = await scraper.fetch_full_detail(url)
            
            # Guardamos los detalles completos en la base de datos.
            await projects_repository.update_full_details(link_hash, full_detail)
            
            proposal  = await ai_service.generate_proposal(full_detail)
            if proposal is not None and "error" not in proposal:

                await projects_repository.update_project_proposal(link_hash, proposal)
                processed_count += 1
                total_usd = proposal.get("summary", {}).get("total_budget", 0)
                await update.message.reply_text(
                        f"✅ **Propuesta Generada**\n"
                        f"📌 {title}\n"
                        f"URL: {url}\n"
                        f"💰 Presupuesto estimado: ${total_usd}\n"
                        f"⏱️ Horas: {proposal.get('summary', {}).get('total_hours')}h"
                    )
        except Exception as e:
            failed_count += 1
            logger.error(f"Error procesando proyecto {title}: {str(e)}")
            await update.message.reply_text(f'Ha habido un error en la IA al procesar el proyecto: {title}')
            break

        
    end_message = f"Fin procesamiento de proyectos. Proyectos procesados: {processed_count}.  Proyectos fallidos: {failed_count}"
    logger.info(end_message)
    await update.message.reply_text(end_message)