import os
import asyncio
import time
from loguru import logger
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
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


def is_network_error(error: Exception) -> bool:
    """
    Determina si una excepción está relacionada con problemas de conectividad de red.
    Incluye errores de conexión, timeout, y errores específicos de Playwright.
    """
    network_error_types = (
        ConnectionError,
        TimeoutError,
        OSError,
        PlaywrightTimeoutError,
    )
    return isinstance(error, network_error_types)


async def process_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    if not update.message:
        return

    await update.message.reply_text("🧠 Obteniendo proyectos pendientes para evaluación con IA...")
    
    projects_repository = get_projects_repository()
    ai_service = get_intelligence_service()

    projects = await projects_repository.get_projects_for_deep_analysis(limit=50)
    if not projects:
        logger.success(f"📭 No hay proyectos pendientes en la base de datos para evaluación inicial.")
        await update.message.reply_text("📭 No hay proyectos pendientes en la base de datos para evaluación inicial.")
        return

    await update.message.reply_text(f"🤖 Evaluando {len(projects)} proyectos con Gemini. Esto puede tardar un momento...")
    scraper = ScraperFactory.get_scraper()

    processed_count = 0
    failed_count = 0
    
    # Circuit Breaker: Contador de fallas consecutivas en memoria
    consecutive_failures = 0
    CIRCUIT_BREAKER_THRESHOLD = 5
    MAX_RETRY_ATTEMPTS = 3

    for project in projects:
        url = project.get('link')
        link_hash = project.get('link_hash')
        title = project.get('title', 'Sin título')
        total_usd = 0

        if not url or not link_hash:
            continue

        retry_count = 0
        project_succeeded = False
        critical_failure = False

        # Exponential Backoff Retry Logic
        while retry_count < MAX_RETRY_ATTEMPTS and not critical_failure:
            try:
                logger.info(f"Extrayendo detalle para: {title} (Intento {retry_count + 1}/{MAX_RETRY_ATTEMPTS})")
                full_detail = await scraper.fetch_full_detail(url)

                # --- INICIO: Cortocircuito para proyectos no encontrados ---
                if full_detail is None:
                    logger.info(f"Proyecto '{title}' no encontrado en la plataforma. Marcando como 'not_found'.")
                    await projects_repository.mark_projects_status([link_hash], "not_found")
                    if update.message:
                        await update.message.reply_text(
                            f"🚫 Proyecto descartado (no encontrado):\n"
                            f"📄 {title}"
                        )
                    # Rompemos el bucle de reintentos y marcamos como "exitoso" para que el `continue` de abajo se active
                    project_succeeded = True
                    break
                # --- FIN: Cortocircuito ---
                
                # Guardamos los detalles completos en la base de datos.
                await projects_repository.update_full_details(link_hash, full_detail)
                
                proposal = await ai_service.generate_proposal(full_detail)
                if proposal is not None and "error" not in proposal:

                    await projects_repository.update_project_proposal(link_hash, proposal)
                    processed_count += 1
                    total_usd = proposal.get("summary", {}).get("total_budget", 0)
                    if update.message:
                        await update.message.reply_text(
                            f"✅ **Propuesta Generada**\n"
                            f"📌 {title}\n"
                            f"URL: {url}\n"
                            f"💰 Presupuesto estimado: ${total_usd}\n"
                            f"⏱️ Horas: {proposal.get('summary', {}).get('total_hours')}h"
                        )
                
                # Proyecto completado exitosamente - resetear contador del circuit breaker
                consecutive_failures = 0
                project_succeeded = True
                break

            except Exception as e:
                retry_count += 1
                
                if is_network_error(e):
                    logger.warning(f"Error de red en proyecto {title} (Intento {retry_count}/{MAX_RETRY_ATTEMPTS}): {str(e)}")
                    
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        # Exponential backoff: 2s, 4s, 8s
                        backoff_time = 2 ** retry_count
                        logger.info(f"Esperando {backoff_time}s antes de reintentar...")
                        await asyncio.sleep(backoff_time)
                    else:
                        # Se agotaron los reintentos por error de red
                        consecutive_failures += 1
                        failed_count += 1
                        logger.error(f"Proyecto {title} omitido tras {MAX_RETRY_ATTEMPTS} intentos fallidos por error de red: {str(e)}")
                        
                        # Notificación silenciosa a Telegram
                        if update.message:
                            await update.message.reply_text(
                                f"⚠️ **Proyecto omitido por error de red**\n"
                                f"📌 {title}\n"
                                f"🔗 {url}\n"
                                f"El proyecto conservará su estado original para reintentos futuros."
                            )
                        
                        # Circuit Breaker Check
                        if consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                            logger.critical(f"Circuit Breaker Activado: {CIRCUIT_BREAKER_THRESHOLD} fallas consecutivas de red detectadas.")
                            if update.message:
                                await update.message.reply_text(
                                    f"🚨 **CIRCUIT BREAKER ACTIVADO**\n"
                                    f"Red caída detectada tras {CIRCUIT_BREAKER_THRESHOLD} fallas consecutivas.\n"
                                    f"Ejecución abortada automáticamente para proteger el sistema."
                                )
                            return
                else:
                    # Error no relacionado con red (ej: error de IA, parsing, etc.)
                    failed_count += 1
                    critical_failure = True
                    logger.error(f"Error no recuperable procesando proyecto {title}: {str(e)}")
                    if update.message:
                        await update.message.reply_text(f'❌ Error crítico en el proyecto {title}: {str(e)}')

        # Si el proyecto se procesó (o se descartó correctamente), continuamos al siguiente
        if project_succeeded:
            continue

        # Si hubo una falla crítica (no relacionada con red), detener el procesamiento
        if critical_failure:
            break

    end_message = f"Fin procesamiento de proyectos. Proyectos procesados: {processed_count}. Proyectos fallidos: {failed_count}"
    logger.info(end_message)
    if update.message:
        await update.message.reply_text(end_message)