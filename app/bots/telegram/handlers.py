import os
import asyncio
import time
from loguru import logger
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import NetworkError as TelegramNetworkError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from app.scraper.factory import ScraperFactory
from app.database import get_projects_repository, get_process_semaphore
from app.intelligence.factory import get_intelligence_service
from .messages import send_long_message
from app.bots.telegram.circuit_breaker import CircuitBreaker
from app.exceptions import (
    AIConnectionError,
    CircuitBreakerWarning,
    CircuitBreakerSuspension,
    CircuitBreakerCritical,
    CircuitBreakerTrippedError,
)



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

    keyboard = [["/status", "/lista" ],["/desbloquear", "/procesar"]]
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
    if not update.message:
        return

    try:
        semaphore = get_process_semaphore()
        if await semaphore.is_locked():
            status_data = await semaphore.get_status()
            if not status_data:
                raise ValueError("El estado del semáforo es nulo o corrupto.")

            remaining_projects = semaphore.calculate_remaining_projects(status_data)
            locked_at_dt = status_data.get("locked_at")
            last_activity_dt = status_data.get("last_activity_at")

            locked_at_str = locked_at_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if locked_at_dt else "N/A"
            last_activity_str = last_activity_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if last_activity_dt else "N/A"

            message = (
                f"🚫 **Acción Denegada: Sistema Ocupado**\n"
                f"El comando `/status` no puede ejecutarse porque el Semáforo Global está activo.\n"
                f"📅 **Bloqueado el:** {locked_at_str}\n"
                f"🔄 **Última Actividad:** {last_activity_str}\n"
                f"📦 **Proyectos Restantes en la Cola:** {remaining_projects}\n\n"
                f"*Espere a que finalice el proceso actual o utilice `/desbloquear` si sospecha de una caída crítica del sistema.*"
            )
            await update.message.reply_text(message, parse_mode="Markdown")
            return

    except Exception as e:
        logger.error(f"Fallo al verificar el estado del semáforo: {e}")
        await update.message.reply_text(
            "⚠️ No se pudo verificar el estado del sistema. Por seguridad, la operación ha sido cancelada."
        )
        return
    
    await update.message.reply_text(
        "📊 **Resumen actual:**\n- Propuestas activas: 0\n- En negociación: 0\n- Connects: 50",
        parse_mode="Markdown",
    )


async def fetch_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return

    if not update.message:
        return

    try:
        semaphore = get_process_semaphore()
        if await semaphore.is_locked():
            status = await semaphore.get_status()
            if not status:
                raise ValueError("El estado del semáforo es nulo o corrupto.")

            remaining_projects = semaphore.calculate_remaining_projects(status)
            locked_at_dt = status.get("locked_at")
            last_activity_dt = status.get("last_activity_at")

            locked_at_str = locked_at_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if locked_at_dt else "N/A"
            last_activity_str = last_activity_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if last_activity_dt else "N/A"

            message = (
                f"🚫 **Acción Denegada: Sistema Ocupado**\n"
                f"El comando `/listar` no puede ejecutarse porque el Semáforo Global está activo.\n"
                f"📅 **Bloqueado el:** {locked_at_str}\n"
                f"🔄 **Última Actividad:** {last_activity_str}\n"
                f"📦 **Proyectos Restantes en la Cola:** {remaining_projects}\n\n"
                f"*Espere a que finalice el proceso actual o utilice `/desbloquear` si sospecha de una caída crítica del sistema.*"
            )
            await update.message.reply_text(message, parse_mode="Markdown")
            return
            
    except Exception as e:
        logger.error(f"Fallo al verificar el estado del semáforo: {e}")
        await update.message.reply_text(
            "⚠️ No se pudo verificar el estado del sistema. Por seguridad, la operación ha sido cancelada."
        )
        return

    projects_repository = get_projects_repository()
    try:
        await update.message.reply_text("🔍 Consultando nuevos proyectos...")
    except Exception as e:
        logger.warning(f"No se pudo enviar notificación inicial a Telegram: {e}")
    
    scraper = ScraperFactory.get_scraper()

    # Validate state file exists before attempting scraping
    if hasattr(scraper, 'state_file'):
        state_path = scraper.state_file
        if not os.path.exists(state_path):
            logger.error(f"❌ Archivo de sesión no encontrado: {state_path}")
            try:
                await update.message.reply_text(
                    "⚠️ Archivo de sesión (state.json) no encontrado. "
                    "Ejecuta `python scripts/extract_session.py` para generar uno. "
                    "Verifica que la variable STATE_FILE_PATH apunte a la ruta correcta."
                )
            except Exception as ne:
                logger.warning(f"No se pudo enviar notificación de sesión faltante a Telegram: {ne}")
            return
        elif os.path.isdir(state_path):
            logger.error(f"❌ La ruta de sesión es un directorio, no un archivo: {state_path}")
            try:
                await update.message.reply_text(
                    "⚠️ La ruta STATE_FILE_PATH apunta a un directorio, no a un archivo. "
                    "Corrige la variable STATE_FILE_PATH en tu archivo .env para que apunte a un archivo "
                    "(ej. /usr/src/app/state.json)."
                )
            except Exception as ne:
                logger.warning(f"No se pudo enviar notificación de directorio inválido a Telegram: {ne}")
            return
        elif not os.path.isfile(state_path):
            logger.error(f"❌ La ruta de sesión no es un archivo regular: {state_path}")
            try:
                await update.message.reply_text(
                    "⚠️ La ruta STATE_FILE_PATH no apunta a un archivo válido. "
                    "Verifica la configuración e intenta nuevamente."
                )
            except Exception as ne:
                logger.warning(f"No se pudo enviar notificación de archivo inválido a Telegram: {ne}")
            return

    try:
        projects = await scraper.get_projects()
    except Exception as e:
        logger.error(f"❌ Error durante el scraping: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "⚠️ Error al buscar proyectos: Hubo un problema con la sesión de navegación. "
                "Intenta nuevamente o verifica el estado del scraper."
            )
        except Exception as ne:
            logger.warning(f"No se pudo enviar notificación de error de scraping a Telegram: {ne}")
        return
    logger.info(f"Se obtuvieron {len(projects)} proyectos del scraping.")

    if not projects:
        try:
            await update.message.reply_text("📭 No se encontraron proyectos nuevos.")
        except Exception as e:
            logger.warning(f"No se pudo enviar notificación a Telegram: {e}")
        return

    save_stats = await projects_repository.save_scraped_projects(projects)
    try:
        await update.message.reply_text(
            f"💾 **Sincronización DB:**\n"
            f"- Nuevos: {save_stats['inserted']}\n"
            f"- Actualizados/Existentes: {save_stats['existing']}"
        )
    except Exception as e:
        logger.warning(f"No se pudo enviar notificación de sincronización a Telegram: {e}")

    ai_service = get_intelligence_service()
    total_processed = 0
    all_relevant = []
    max_iterations = 10
    buffer_size = 10
    iterations = 0
    
    # Obtenemos la cantidad total de proyectos pendientes ANTES de procesarlos
    # usamos count_documents que es más eficiente y directo
    pending_count = await projects_repository.collection.count_documents({"proposal_status": "pending"})
    
    delay_before_eval = float(os.getenv("DELAY_BEFORE_EVALUATION", "30"))
    try:
        await update.message.reply_text(f"🧠 Hay {pending_count} proyectos pendientes en DB.\nSe evaluarán en lotes en {delay_before_eval} segundos.")
    except Exception as e:
        logger.warning(f"No se pudo enviar notificación de proyectos pendientes a Telegram: {e}")

    await asyncio.sleep(delay_before_eval)
    while iterations < max_iterations:
        iterations += 1
        # Recuperamos un lote para no saturar la memoria ni la API de la IA
        batch = await projects_repository.claim_pending_projects(limit=buffer_size)
        
        if not batch:
            logger.info("No hay proyectos pendientes.  Batch dio Null o 0")
            break # Ya no quedan proyectos 'pending'

        link_hashes = [p["link_hash"] for p in batch]

        try:
            try:
                await update.message.reply_text(f"🧠 Iniciando la evaluación del Lote #{iterations} con {buffer_size} proyectos.")
            except Exception as e:
                logger.warning(f"No se pudo enviar notificación de inicio de lote a Telegram: {e}")
            
            await projects_repository.mark_projects_status(link_hashes, "processing")
            delay_between_batches = float(os.getenv("DELAY_BETWEEN_BATCHES", "4"))
            await asyncio.sleep(delay_between_batches)
            evaluations =  await ai_service.evaluate_projects(batch)
        except Exception as e:
            logger.critical(f"Abortando: Error de infraestructura en IA: {e}", exc_info=True)
            # Revertir el lote actual a pending para que no queden atascados en processing
            await projects_repository.mark_projects_status(link_hashes, "pending")
            try:
                await update.message.reply_text(f"❌ Error crítico: {e}. El proceso se ha detenido para proteger los datos.")
            except Exception as ne:
                logger.warning(f"No se pudo enviar notificación de error crítico a Telegram: {ne}")
            break

        for project, eval_data in zip(batch, evaluations):
            reason = eval_data.get("reason", 'Sin razón especificada.')
            error_msg = eval_data.get("error")

            # Si la IA reporta un error, lo registramos y devolvemos el proyecto a pending
            if error_msg or "error" in reason.lower():
                logger.error(f"Error en evaluación de IA para proyecto {project.get('link_hash')}: {error_msg or reason}")
                await projects_repository.mark_projects_status([project["link_hash"]], "pending")
                continue

            score = eval_data.get("score", 0)
            strategy = eval_data.get("strategy", "none")
            summary = eval_data.get("summary", "No summary available.")
            contract_type = eval_data.get("contract_type", "project_fixed")
            
            # Actualizamos resultado en DB
            await projects_repository.update_project_analysis(
                link_hash=project["link_hash"], 
                score=score, 
                reason=reason,
                strategy=strategy,
                status="analyzed",
                ai_summary=summary,
                contract_type=contract_type
            )

            if score > 4:
                all_relevant.append({**project, **eval_data})

        total_processed += len(batch)
        logger.info(f"Lote de {len(batch)} procesado. Total acumulado: {total_processed}")

    # Notificar finalización del análisis
    if not all_relevant:
        try:
            await update.message.reply_text(
                f"✅ **Análisis Completado**\n\n"
                f"📊 Proyectos analizados: {total_processed}\n"
                f"⭐ Con score > 6: 0\n\n"
                f"No se encontraron oportunidades destacadas en este lote."
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar notificación final a Telegram: {e}")
        return

    msg = f"🚀 **{len(all_relevant)} Oportunidades encontradas (de {total_processed} analizados):**\n\n"
    for p in all_relevant:
        contract_emoji = "🔧" if p.get('contract_type') == "staff_augmentation" else "📦"
        contract_label = "Staff Aug." if p.get('contract_type') == "staff_augmentation" else "Proyecto"
        msg += (
            f"⭐ **Score: {p.get('score', 0)}/10** | {contract_emoji} {contract_label}\n"
            f"📌 {p.get('title', 'Sin título')}\n"
            f"💰 {p.get('budget', 'Presupuesto no especificado')}\n"
            f"📝 {p.get('summary', 'No summary')}\n"
            f"💡 {p.get('reason', 'Sin razón')}\n"
            f"🔗 [Ver Proyecto]({p.get('link', '')})\n\n"
        )
    
    msg += f"🏁 **Fin de la lista: {len(all_relevant)} oportunidades encontradas.**"

    try:
        await send_long_message(update, msg)
    except Exception as e:
        logger.warning(f"Error al intentar enviar el reporte de oportunidades a Telegram: {e}")







# ... (other imports remain the same)
...
async def process_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return
    if not update.message:
        return

    projects_repository = get_projects_repository()
    semaphore = get_process_semaphore()
    ai_service = get_intelligence_service()

    # FASE 1: VERIFICACIÓN DEL SEMÁFORO GLOBAL
    if await semaphore.is_locked():
        status = await semaphore.get_status()
        if status:
            telemetry_message = semaphore.format_telemetry_message(status)
            await update.message.reply_text(telemetry_message, parse_mode="Markdown")
        else:
            await update.message.reply_text("🔒 El proceso ya está en ejecución.")
        return

    # FASE 2: RESET DE PROYECTOS HUÉRFANOS
    await update.message.reply_text("🔄 Limpiando proyectos huérfanos...")
    reset_count = await projects_repository.reset_orphaned_proposals()
    if reset_count > 0:
        await update.message.reply_text(f"✅ {reset_count} proyectos reseteados.")

    # FASE 3: OBTENER PROYECTOS Y ADQUIRIR SEMÁFORO
    await update.message.reply_text("🧠 Obteniendo proyectos con alto score...")
    projects = await projects_repository.get_projects_for_deep_analysis(limit=50)
    
    if not projects:
        logger.success("📭 No hay proyectos para procesar.")
        await update.message.reply_text("📭 No hay proyectos que requieran propuesta.")
        return

    if not await semaphore.acquire(total_projects=len(projects)):
        await update.message.reply_text("⛔ No se pudo adquirir el semáforo.")
        return

    # FASE 4: PROCESAMIENTO CON SEMÁFORO Y CIRCUIT BREAKER
    await update.message.reply_text(
        f"🤖 Iniciando para {len(projects)} proyectos...\n🔒 Semáforo activado."
    )
    scraper = ScraperFactory.get_scraper()

    processed_count = 0
    failed_count = 0
    not_found_count = 0
    
    circuit_breaker = CircuitBreaker()
    MAX_SCRAPE_ATTEMPTS = 3

    for i, project in enumerate(projects):
        url = project.get('link')
        link_hash = project.get('link_hash')
        title = project.get('title', 'Sin título')
        
        if not url or not link_hash:
            continue

        try:
            await update.message.reply_text(f"⚙️ ({i+1}/{len(projects)}) Procesando: {title}")
        except TelegramNetworkError as e:
            logger.warning(f"No se pudo notificar inicio a Telegram: {e}")

        try:
            # --- Bloque de Lógica de Procesamiento por Proyecto ---
            scrape_retry = 0
            full_detail = None
            while scrape_retry < MAX_SCRAPE_ATTEMPTS:
                try:
                    logger.info(f"Extrayendo detalle para: {title} (Intento {scrape_retry + 1}/{MAX_SCRAPE_ATTEMPTS})")
                    full_detail = await scraper.fetch_full_detail(url)
                    break 
                except PlaywrightTimeoutError as e:
                    scrape_retry += 1
                    logger.warning(f"Timeout de scraping en {title} (Intento {scrape_retry}): {e}")
                    if scrape_retry < MAX_SCRAPE_ATTEMPTS:
                        await asyncio.sleep(2 ** scrape_retry)
                    else:
                        logger.error(f"Fallo definitivo de scraping para {title}.")
                        raise e # Lanza la excepción para que sea capturada por el manejador principal del proyecto

            if full_detail is None:
                logger.info(f"Proyecto '{title}' no encontrado. Marcando como 'not_found'.")
                await projects_repository.mark_projects_status([link_hash], "not_found")
                not_found_count += 1
                await semaphore.update_activity(processed_count, failed_count, not_found_count)
                continue

            raw_description = full_detail.get("full_description")
            if raw_description:
                formatted_description = await ai_service.format_project_description(
                    raw_description, circuit_breaker=circuit_breaker
                )
                full_detail["full_description"] = formatted_description

            # Guardamos los detalles completos, incluyendo la descripción formateada
            await projects_repository.update_full_details(link_hash, full_detail)

            full_detail.update({
                "contract_type": project.get("contract_type", "project_fixed"),
                "strategy": project.get("strategy", "none")
            })

            proposal = await ai_service.generate_proposal(full_detail, circuit_breaker=circuit_breaker)
            
            if proposal and "error" not in proposal:
                await projects_repository.update_project_proposal(link_hash, proposal)
                processed_count += 1
                # Notificación de éxito...
            else:
                failed_count += 1
                await semaphore.update_activity(processed_count, failed_count, not_found_count)
                logger.error(f"Error de la IA al generar propuesta para {title}: {proposal.get('error', 'Unknown') if proposal else 'None'}")
        
        except CircuitBreakerWarning as e:
            failed_count += 1
            await semaphore.update_activity(processed_count, failed_count, not_found_count)
            await update.message.reply_text(f"⚠️ {str(e)}")
            await asyncio.sleep(e.backoff_duration * 60)
            continue
        
        except CircuitBreakerSuspension as e:
            failed_count += 1
            await semaphore.update_activity(processed_count, failed_count, not_found_count)
            await update.message.reply_text(f"⏳ {str(e)}")
            await asyncio.sleep(e.backoff_duration * 60)
            continue

        except CircuitBreakerCritical as e:
            failed_count += 1
            await semaphore.update_activity(processed_count, failed_count, not_found_count)
            await update.message.reply_text(f"‼️ {str(e)}")
            await asyncio.sleep(e.backoff_duration * 60)
            continue

        except CircuitBreakerTrippedError as e:
            await update.message.reply_text(
                "⚠️ Bot apagado por inestabilidad persistente en la API de IA. "
                "El sistema permanece bloqueado de forma segura. Utilice el "
                "comando administrativo /desbloquear una vez estabilizado el servicio."
            )
            logger.critical(f"APAGADO DEFINITIVO: {str(e)}")
            return # SALIDA DE EMERGENCIA SIN LIBERAR SEMÁFORO

        except AIConnectionError:
            failed_count += 1
            await semaphore.update_activity(processed_count, failed_count, not_found_count)
            logger.error(f"Falla de IA (falla #{circuit_breaker.consecutive_failures}) procesando '{title}'. Continuando.")
            continue

        except Exception as e:
            failed_count += 1
            await semaphore.update_activity(processed_count, failed_count, not_found_count)
            logger.critical(f"Error no recuperable procesando proyecto {title}: {e}", exc_info=True)
            await update.message.reply_text(f'❌ Error crítico en: {title}. Omitiendo.')
            continue

        # Actualizar telemetría tras un éxito
        await semaphore.update_activity(processed_count, failed_count, not_found_count)

    # FASE 5: LIBERACIÓN DEL SEMÁFORO
    await semaphore.release()
    logger.success("🔓 Semáforo global liberado automáticamente")

    end_message = (
        f"🏁 **Proceso Finalizado** 🏁\n\n"
        f"✅ Propuestas generadas: {processed_count}\n"
        f"🚫 No encontrados: {not_found_count}\n"
        f"❌ Fallidos: {failed_count}\n"
        f"--------------------\n"
        f"Total: {len(projects)}"
    )
    await update.message.reply_text(end_message, parse_mode="Markdown")




async def unlock_semaphore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando administrativo de escape para liberar el semáforo global manualmente.
    Útil en casos de fallas críticas de infraestructura o procesos congelados.
    """
    if not await is_admin(update):
        return
    if not update.message:
        return

    semaphore = get_process_semaphore()
    
    # Obtener estado antes de liberar
    status = await semaphore.get_status()
    was_locked = status.get("is_locked", False) if status else False
    
    # Liberación forzada (idempotente)
    await semaphore.force_release()
    
    if was_locked:
        await update.message.reply_text(
            "🔓 **Semáforo Global liberado manualmente**\n\n"
            "El comando /procesar vuelve a estar disponible.\n\n"
            "⚠️ NOTA: Si había un proceso en ejecución, puede quedar en estado inconsistente.",
            parse_mode="Markdown"
        )
        logger.warning("⚠️ Semáforo liberado manualmente por comando administrativo")
    else:
        await update.message.reply_text(
            "ℹ️ El semáforo ya estaba liberado.\n"
            "Operación completada (idempotente)."
        )
        logger.info("ℹ️ Comando /desbloquear ejecutado con semáforo ya liberado")
