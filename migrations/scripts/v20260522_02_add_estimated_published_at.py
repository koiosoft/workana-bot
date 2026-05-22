
import re
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import cast

from pymongo.database import Database
from pymongo.errors import OperationFailure

from migrations.core.base import IMigrationContext, MigrationBase
from migrations.core.writer import ResilientBulkWriter

logger = getLogger(__name__)

class Migration(MigrationBase):
    """
    Calcula y almacena la fecha de publicación estimada (`estimated_published_at`)
    para los proyectos basándose en el tiempo relativo extraído por el scraper.
    """

    def up(self, writer: IMigrationContext) -> None:
        """
        Aplica la migración: lee, calcula y encola las actualizaciones de documentos.
        Además, crea un índice para optimizar futuras consultas.
        """
        # Se realiza un cast para acceder a atributos de la implementación concreta
        # que no están en la interfaz del protocolo, como `.db`.
        concrete_writer = cast(ResilientBulkWriter, writer)
        db = concrete_writer.db
        
        # Patrones de Regex para parsear el tiempo relativo, manejando singular y plural.
        time_patterns = {
            'months': re.compile(r"hace\s+(?P<value>\d+)\s+mes(es)?", re.IGNORECASE),
            'days': re.compile(r"hace\s+(?P<value>\d+)\s+d[íi]a(s)?", re.IGNORECASE),
            'hours': re.compile(r"hace\s+(?P<value>\d+)\s+hora(s)?", re.IGNORECASE),
            'minutes': re.compile(r"hace\s+(?P<value>\d+)\s+minuto(s)?", re.IGNORECASE),
            'moment': re.compile(r"hace\s+(un\s+momento|menos\s+de\s+un\s+minuto)", re.IGNORECASE)
        }

        cursor = db.projects.find({})

        for doc in cursor:
            if "estimated_published_at" in doc and isinstance(doc.get("estimated_published_at"), datetime):
                continue

            scraped_at_val = doc.get("scraped_at")
            published_str = doc.get("published")

            if not all([scraped_at_val, published_str]):
                logger.warning(f"Documento con _id={doc['_id']} omitido: 'scraped_at' o 'published' ausentes.")
                continue

            try:
                if isinstance(scraped_at_val, str):
                    scraped_at = datetime.fromisoformat(scraped_at_val)
                elif isinstance(scraped_at_val, datetime):
                    scraped_at = scraped_at_val
                else:
                    raise TypeError(f"Tipo inesperado para 'scraped_at': {type(scraped_at_val)}")

                if scraped_at.tzinfo is None:
                    scraped_at = scraped_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as e:
                logger.error(f"Error al parsear 'scraped_at' en doc _id={doc['_id']}: {e}")
                continue

            delta = None
            
            if 'ayer' in published_str.lower():
                delta = timedelta(days=1)
            else:
                for unit, pattern in time_patterns.items():
                    match = pattern.search(published_str)
                    if match:
                        if unit == 'moment':
                            delta = timedelta(minutes=1)
                        else:
                            value = int(match.group('value'))
                            if unit == 'months':
                                # Aproximación: se asume que un mes tiene 30 días.
                                delta = timedelta(days=value * 30)
                            else:
                                delta = timedelta(**{unit: value})
                        break
            
            if delta is None:
                logger.warning(f"No se pudo parsear el tiempo relativo '{published_str}' en doc _id={doc['_id']}. Se omite.")
                continue

            estimated_date = scraped_at - delta
            writer.add_update(
                collection_name="projects",
                filter_query={"_id": doc["_id"]},
                update_query={"$set": {"estimated_published_at": estimated_date}}
            )

        logger.info("Creando índice en 'estimated_published_at'...")
        try:
            db.projects.create_index([("estimated_published_at", -1)], name="estimated_published_at_-1")
            logger.info("Índice 'estimated_published_at_-1' creado exitosamente.")
        except OperationFailure as e:
            if "already exists" in str(e):
                logger.warning("El índice 'estimated_published_at_-1' ya existía.")
            else:
                raise

    def down(self, db: Database) -> None:
        """
        Revierte la migración: elimina el campo de todos los documentos
        y elimina el índice asociado.
        """
        try:
            db.projects.drop_index("estimated_published_at_-1")
            logger.info("Índice 'estimated_published_at_-1' eliminado.")
        except OperationFailure:
            logger.warning("No se pudo eliminar el índice 'estimated_published_at_-1' (probablemente no existía).")

        logger.info("Eliminando el campo 'estimated_published_at' de la colección 'projects'...")
        result = db.projects.update_many({}, {"$unset": {"estimated_published_at": ""}})
        logger.info(f"{result.modified_count} documentos fueron actualizados para eliminar el campo.")
