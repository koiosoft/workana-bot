"""
Semáforo Global para control de concurrencia del proceso de generación de propuestas.
Proporciona bloqueo atómico, telemetría detallada y comando de escape administrativo.
"""
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from pymongo import ASCENDING
from .mongo import get_database
from loguru import logger


class ProcessSemaphore:
    """
    Semáforo global persistente en MongoDB para control de concurrencia.
    Garantiza que solo una instancia del proceso /procesar pueda ejecutarse simultáneamente.
    """
    
    COLLECTION_NAME = "process_semaphore"
    LOCK_ID = "proposal_generation_lock"
    
    def __init__(self):
        self._indexes_ready = False
    
    @property
    def collection(self):
        """Obtiene la colección de forma dinámica."""
        return get_database()[self.COLLECTION_NAME]
    
    async def ensure_indexes(self):
        """Crea índices necesarios para la colección del semáforo."""
        if self._indexes_ready:
            return
        await self.collection.create_index([("lock_id", ASCENDING)], unique=True)
        self._indexes_ready = True
    
    async def acquire(self, total_projects: int = 0) -> bool:
        """
        Intenta adquirir el semáforo global.
        
        Args:
            total_projects: Cantidad total de proyectos en la cola inicial
            
        Returns:
            True si se adquirió el bloqueo, False si ya está bloqueado
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc)
        
        try:
            # Intento atómico de inserción (upsert con condición)
            result = await self.collection.update_one(
                {
                    "lock_id": self.LOCK_ID,
                    "$or": [
                        {"is_locked": False},
                        {"is_locked": {"$exists": False}}
                    ]
                },
                {
                    "$set": {
                        "is_locked": True,
                        "locked_at": now,
                        "last_activity_at": now,
                        "total_projects": total_projects,
                        "processed_count": 0,
                        "failed_count": 0,
                        "not_found_count": 0
                    }
                },
                upsert=True
            )
            
            acquired = result.modified_count > 0 or result.upserted_id is not None
            
            if acquired:
                logger.success(f"🔒 Semáforo global adquirido. Total proyectos: {total_projects}")
            else:
                logger.warning("⛔ Semáforo global ya está bloqueado por otro proceso")
            
            return acquired
            
        except Exception as e:
            logger.error(f"Error al intentar adquirir semáforo: {e}")
            return False
    
    async def release(self) -> bool:
        """
        Libera el semáforo global al finalizar el proceso.
        
        Returns:
            True si se liberó exitosamente
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc)
        
        result = await self.collection.update_one(
            {"lock_id": self.LOCK_ID},
            {
                "$set": {
                    "is_locked": False,
                    "released_at": now
                }
            }
        )
        
        if result.modified_count > 0:
            logger.success("🔓 Semáforo global liberado correctamente")
            return True
        
        logger.warning("⚠️ No se pudo liberar el semáforo (posiblemente ya estaba liberado)")
        return False
    
    async def update_activity(self, processed: int = 0, failed: int = 0, not_found: int = 0) -> bool:
        """
        Actualiza las métricas de actividad del proceso en ejecución.
        
        Args:
            processed: Cantidad de proyectos procesados exitosamente
            failed: Cantidad de proyectos que fallaron
            not_found: Cantidad de proyectos no encontrados
            
        Returns:
            True si se actualizó correctamente
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc)
        
        result = await self.collection.update_one(
            {"lock_id": self.LOCK_ID, "is_locked": True},
            {
                "$set": {
                    "last_activity_at": now,
                    "processed_count": processed,
                    "failed_count": failed,
                    "not_found_count": not_found
                }
            }
        )
        
        return result.modified_count > 0
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado actual del semáforo con toda su telemetría.
        
        Returns:
            Diccionario con el estado completo del semáforo o None si no existe
        """
        await self.ensure_indexes()
        doc = await self.collection.find_one({"lock_id": self.LOCK_ID})
        
        if not doc:
            return None
        
        return {
            "is_locked": doc.get("is_locked", False),
            "locked_at": doc.get("locked_at"),
            "last_activity_at": doc.get("last_activity_at"),
            "total_projects": doc.get("total_projects", 0),
            "processed_count": doc.get("processed_count", 0),
            "failed_count": doc.get("failed_count", 0),
            "not_found_count": doc.get("not_found_count", 0),
            "released_at": doc.get("released_at")
        }
    
    async def is_locked(self) -> bool:
        """
        Verifica si el semáforo está actualmente bloqueado.
        
        Returns:
            True si está bloqueado, False en caso contrario
        """
        await self.ensure_indexes()
        doc = await self.collection.find_one({"lock_id": self.LOCK_ID})
        
        if not doc:
            return False
        
        return doc.get("is_locked", False)
    
    async def force_release(self) -> bool:
        """
        Libera el semáforo de forma forzada (comando de escape administrativo).
        Esta operación es idempotente y puede ejecutarse en cualquier momento.
        
        Returns:
            True siempre (operación idempotente)
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc)
        
        result = await self.collection.update_one(
            {"lock_id": self.LOCK_ID},
            {
                "$set": {
                    "is_locked": False,
                    "force_released_at": now,
                    "released_at": now
                }
            },
            upsert=True
        )
        
        logger.warning(f"🔓 Semáforo liberado MANUALMENTE (force_release). Modified: {result.modified_count}, Upserted: {result.upserted_id}")
        return True
    
    def calculate_remaining_projects(self, status: Dict[str, Any]) -> int:
        """
        Calcula la cantidad de proyectos restantes en la cola.
        
        Args:
            status: Diccionario con el estado actual del semáforo
            
        Returns:
            Cantidad de proyectos restantes por procesar
        """
        total = status.get("total_projects", 0)
        processed = status.get("processed_count", 0)
        failed = status.get("failed_count", 0)
        not_found = status.get("not_found_count", 0)
        
        remaining = total - (processed + failed + not_found)
        return max(0, remaining)
    
    def format_telemetry_message(self, status: Dict[str, Any]) -> str:
        """
        Formatea un mensaje de telemetría detallado para Telegram.
        
        Args:
            status: Diccionario con el estado actual del semáforo
            
        Returns:
            Mensaje formateado con toda la información del bloqueo
        """
        locked_at = status.get("locked_at")
        last_activity = status.get("last_activity_at")
        remaining = self.calculate_remaining_projects(status)
        
        # Formatear fechas
        locked_str = "N/A"
        activity_str = "N/A"
        
        if locked_at:
            if isinstance(locked_at, datetime):
                locked_str = locked_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                locked_str = str(locked_at)
        
        if last_activity:
            if isinstance(last_activity, datetime):
                activity_str = last_activity.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                activity_str = str(last_activity)
        
        message = (
            "🔒 **BLOQUEADO** - Generación de propuestas en ejecución\n\n"
            f"📅 **Bloqueado desde:** {locked_str}\n"
            f"⏱️ **Última actividad:** {activity_str}\n"
            f"📊 **Proyectos restantes:** {remaining}/{status.get('total_projects', 0)}\n\n"
            f"✅ Procesados: {status.get('processed_count', 0)}\n"
            f"❌ Fallidos: {status.get('failed_count', 0)}\n"
            f"🚫 No encontrados: {status.get('not_found_count', 0)}"
        )
        
        return message


# Singleton global
_semaphore_instance: ProcessSemaphore | None = None


def get_process_semaphore() -> ProcessSemaphore:
    """
    Retorna una instancia singleton del semáforo de proceso.
    La instancia se crea en la primera llamada.
    """
    global _semaphore_instance
    if _semaphore_instance is None:
        _semaphore_instance = ProcessSemaphore()
    return _semaphore_instance
