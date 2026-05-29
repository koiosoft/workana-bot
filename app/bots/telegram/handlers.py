import os
import asyncio
import time
from loguru import logger
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import NetworkError as TelegramNetworkError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from google.genai.errors import APIError as GeminiAPIError
import httpx
from app.scraper.factory import ScraperFactory
from app.database import get_projects_repository, get_process_semaphore
from app.intelligence.factory import get_intelligence_service
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
    projects = await scraper.get_projects()
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
    
    try:
        await update.message.reply_text(f"🧠 Hay {pending_count} proyectos pendientes en DB.\nSe evaluarán en lotes en 30 segundos.")
    except Exception as e:
        logger.warning(f"No se pudo enviar notificación de proyectos pendientes a Telegram: {e}")

    await asyncio.sleep(30)
    while iterations < max_iterations:
        iterations += 1
        # Recuperamos un lote para no saturar la memoria ni la API de la IA
        batch = await projects_repository.claim_pending_projects(limit=buffer_size)
        
        if not batch:
            logger.info("No hay proyectos pendientes.  Batch dio Null o 0")
            break # Ya no quedan proyectos 'pending'

        try:
            try:
                await update.message.reply_text(f"🧠 Iniciando la evaluación del Lote #{iterations} con {buffer_size} proyectos.")
            except Exception as e:
                logger.warning(f"No se pudo enviar notificación de inicio de lote a Telegram: {e}")
            link_hashes = [p["link_hash"] for p in batch]
            await projects_repository.mark_projects_status(link_hashes, "processing")
            await asyncio.sleep(4)
            evaluations =  await ai_service.evaluate_projects(batch)
        except Exception as e:
            logger.critical(f"Abortando: Error de infraestructura en IA: {e}")
            try:
                await update.message.reply_text(f"❌ Error crítico: {e}. El proceso se ha detenido para proteger los datos.")
            except Exception as ne:
                logger.warning(f"No se pudo enviar notificación de error crítico a Telegram: {ne}")
            break

        for project, eval_data in zip(batch, evaluations):
            score = eval_data.get("score", 0)
            strategy = eval_data.get("strategy", "none")
            summary = eval_data.get("summary", "No summary available.")
            contract_type = eval_data.get("contract_type", "project_fixed")
            
            # Actualizamos resultado en DB
            await projects_repository.update_project_analysis(
                link_hash=project["link_hash"], 
                score=score, 
                reason=eval_data.get("reason", 'Sin razón especificada.'),
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


def is_retriable_error(error: Exception) -> bool:
    """
    Determina si una excepción es retriable.
    Incluye errores de red, timeouts, y errores 5xx de la API de Google.
    """
    retriable_error_types = (
        ConnectionError,
        TimeoutError,
        OSError,
        PlaywrightTimeoutError,
        GeminiAPIError,
        TelegramNetworkError,
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ReadTimeout,
    )
    return isinstance(error, retriable_error_types)


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
            await update.message.reply_text(
                "🔒 El proceso de generación de propuestas ya está en ejecución."
            )
        return

    # FASE 2: RESET DE PROYECTOS HUÉRFANOS
    await update.message.reply_text("🔄 Limpiando proyectos huérfanos...")
    reset_count = await projects_repository.reset_orphaned_proposals()
    if reset_count > 0:
        await update.message.reply_text(f"✅ {reset_count} proyectos resetados de 'ready_for_proposal' a 'analyzed'")

    # FASE 3: OBTENER PROYECTOS Y ADQUIRIR SEMÁFORO
    await update.message.reply_text("🧠 Obteniendo proyectos con alto score para análisis profundo...")
    projects = await projects_repository.get_projects_for_deep_analysis(limit=50)
    
    if not projects:
        logger.success("📭 No hay proyectos listos para la fase de propuesta.")
        await update.message.reply_text("📭 No hay proyectos que requieran generación de propuesta.")
        return

    # Adquirir semáforo
    if not await semaphore.acquire(total_projects=len(projects)):
        await update.message.reply_text(
            "⛔ No se pudo adquirir el semáforo. Otro proceso se inició simultáneamente."
        )
        return

    # FASE 4: PROCESAMIENTO CON SEMÁFORO ACTIVO
    await update.message.reply_text(
        f"🤖 Iniciando generación de propuestas para {len(projects)} proyectos...\n"
        f"🔒 Semáforo global activado."
    )
    scraper = ScraperFactory.get_scraper()

    processed_count = 0
    failed_count = 0
    not_found_count = 0
    
    consecutive_failures = 0
    CIRCUIT_BREAKER_THRESHOLD = 5
    MAX_RETRY_ATTEMPTS = 3

    for i, project in enumerate(projects):
        url = project.get('link')
        link_hash = project.get('link_hash')
        title = project.get('title', 'Sin título')
        contract_type = project.get('contract_type', 'project_fixed')
        contract_emoji = "🔧" if contract_type == "staff_augmentation" else "📦"
        
        if not url or not link_hash:
            continue

        # Notificar inicio de procesamiento (con protección contra errores de red)
        try:
            if update.message:
                await update.message.reply_text(f"⚙️ ({i+1}/{len(projects)}) Procesando {contract_emoji}: {title}")
        except Exception as notification_error:
            logger.warning(f"No se pudo enviar notificación de inicio a Telegram: {notification_error}")

        retry_count = 0
        project_succeeded = False
        critical_failure = False

        while retry_count < MAX_RETRY_ATTEMPTS and not critical_failure:
            try:
                logger.info(f"Extrayendo detalle para: {title} (Intento {retry_count + 1}/{MAX_RETRY_ATTEMPTS})")
                full_detail = await scraper.fetch_full_detail(url)

                if full_detail is None:
                    logger.info(f"Proyecto '{title}' no encontrado en la plataforma. Marcando como 'not_found'.")
                    await projects_repository.mark_projects_status([link_hash], "not_found")
                    try:
                        if update.message:
                            await update.message.reply_text(f"🚫 ({i+1}/{len(projects)}) Descartado (no encontrado): {title}")
                    except Exception as notification_error:
                        logger.warning(f"No se pudo enviar notificación de proyecto no encontrado: {notification_error}")
                    not_found_count += 1
                    project_succeeded = True
                    break
                
                # Interceptación para formatear la descripción
                raw_description = full_detail.get("full_description")
                if raw_description:
                    logger.info(f"Formateando descripción para: {title}")
                    formatted_description = await ai_service.format_project_description(raw_description)
                    full_detail["full_description"] = formatted_description

                await projects_repository.update_full_details(link_hash, full_detail)
                
                try:
                    if update.message:
                        await update.message.reply_text(f"🧠 ({i+1}/{len(projects)}) Generando propuesta IA para: {title}")
                except Exception as notification_error:
                    logger.warning(f"No se pudo enviar notificación de generación a Telegram: {notification_error}")

                # Agregamos el contract_type al full_detail antes de generar la propuesta
                full_detail["contract_type"] = project.get("contract_type", "project_fixed")
                full_detail["strategy"] = project.get("strategy", "none")
                
                proposal = await ai_service.generate_proposal(full_detail)
                if proposal and "error" not in proposal:
                    await projects_repository.update_project_proposal(link_hash, proposal)
                    processed_count += 1
                    
                    # Mostramos información diferente según el tipo de contrato
                    contract_type = full_detail.get("contract_type", "project_fixed")
                    if contract_type == "staff_augmentation":
                        budget_info = proposal.get("budget_summary", {})
                        hourly = budget_info.get("hourly_rate", 0)
                        monthly = budget_info.get("estimated_monthly_budget", 0)
                        try:
                            if update.message:
                                await update.message.reply_text(
                                    f"✅ ({i+1}/{len(projects)}) Propuesta Generada (🔧 Staff): {title}\n"
                                    f"💰 ${hourly}/hora | 📅 ~${monthly}/mes"
                                )
                        except Exception as notification_error:
                            logger.warning(f"No se pudo enviar notificación de éxito (Staff) a Telegram: {notification_error}")
                    else:
                        total_usd = proposal.get("summary", {}).get("total_budget", 0)
                        total_hours = proposal.get("summary", {}).get("total_hours", 0)
                        try:
                            if update.message:
                                await update.message.reply_text(
                                    f"✅ ({i+1}/{len(projects)}) Propuesta Generada (📦 Proyecto): {title}\n"
                                    f"💰 Presupuesto: ${total_usd} | ⏱️ Horas: {total_hours}h"
                                )
                        except Exception as notification_error:
                            logger.warning(f"No se pudo enviar notificación de éxito (Proyecto) a Telegram: {notification_error}")
                else:
                    # Si la IA devuelve un error, lo contamos como fallo
                    failed_count += 1
                    logger.error(f"Error de la IA al generar propuesta para {title}: {proposal.get('error', 'Unknown') if proposal else 'None'}")
                    try:
                        if update.message:
                            await update.message.reply_text(f"❌ ({i+1}/{len(projects)}) Error IA en: {title}")
                    except Exception as notification_error:
                        logger.warning(f"No se pudo enviar notificación de error IA a Telegram: {notification_error}")

                consecutive_failures = 0
                project_succeeded = True
                break

            except Exception as e:
                retry_count += 1
                
                if is_retriable_error(e):
                    logger.warning(f"Error retriable en proyecto {title} (Intento {retry_count}/{MAX_RETRY_ATTEMPTS}): {str(e)}")
                    
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        backoff_time = 2 ** retry_count
                        logger.info(f"Esperando {backoff_time}s antes de reintentar...")
                        await asyncio.sleep(backoff_time)
                    else:
                        consecutive_failures += 1
                        failed_count += 1
                        logger.error(f"Proyecto {title} omitido tras {MAX_RETRY_ATTEMPTS} intentos por error retriable.")
                        try:
                            if update.message:
                                await update.message.reply_text(f"⚠️ ({i+1}/{len(projects)}) Omitido por error persistente: {title}")
                        except Exception as notification_error:
                            logger.warning(f"No se pudo enviar notificación de omisión a Telegram: {notification_error}")
                        
                        if consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                            logger.critical(f"Circuit Breaker Activado: {consecutive_failures} fallas consecutivas.")
                            try:
                                if update.message:
                                    await update.message.reply_text("🚨 **CIRCUIT BREAKER ACTIVADO** 🚨\nFallas consecutivas. Proceso abortado.")
                            except Exception as notification_error:
                                logger.critical(f"No se pudo enviar notificación de circuit breaker: {notification_error}")
                            # No liberamos semáforo aquí para revisión manual
                            return
                else:
                    failed_count += 1
                    critical_failure = True
                    logger.error(f"Error no recuperable procesando proyecto {title}: {str(e)}", exc_info=True)
                    try:
                        if update.message:
                            await update.message.reply_text(f'❌ ({i+1}/{len(projects)}) Error crítico en: {title}. Proceso detenido.')
                    except Exception as notification_error:
                        logger.critical(f"No se pudo enviar notificación de error crítico: {notification_error}")

        if project_succeeded:
            continue
        if critical_failure:
            break

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
    logger.info(end_message)
    try:
        if update.message:
            await update.message.reply_text(end_message, parse_mode="Markdown")
    except Exception as notification_error:
        logger.error(f"No se pudo enviar resumen final a Telegram: {notification_error}")


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