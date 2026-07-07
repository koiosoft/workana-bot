"""Migracion: Agrega el campo 'source_of_changes' a todos los documentos existentes
en 'proposal_versions' que no lo tengan, estableciendo su valor a "IA".

Reglas de negocio:
  - Todos los documentos existentes en proposal_versions fueron generados por el
    modelo de IA (Telegram bot), por lo que corresponde el valor "IA".
  - Los documentos que ya tengan el campo no seran modificados.
  - Se utiliza una operacion UpdateMany para minimizar el impacto en la base de datos.
"""

from loguru import logger
from pymongo.database import Database

from migrations.core.base import IMigrationContext, MigrationBase

TARGET_COLLECTION = "proposal_versions"


class Migration(MigrationBase):
    """
    Backfill del campo 'source_of_changes' en la coleccion proposal_versions.

    Todos los documentos existentes (previos a la introduccion de este campo)
    se marcan con "IA", ya que fueron generados por el bot de Telegram.
    Los nuevos documentos ya incluyen el campo desde su insercion via el
    repositorio.
    """

    def up(self, writer: IMigrationContext) -> None:
        logger.info(
            "Iniciando backfill de 'source_of_changes' en proposal_versions."
        )

        # UpdateMany: agrega source_of_changes = "IA" a todos los documentos
        # que no tengan el campo (o lo tengan como null)
        writer.add_update(
            TARGET_COLLECTION,
            filter_query={"source_of_changes": {"$exists": False}},
            update_query={"$set": {"source_of_changes": "IA"}},
        )

        logger.info(
            "Backfill de 'source_of_changes' encolado exitosamente."
        )

    def down(self, db: Database) -> None:
        """
        Reversion programatica.

        La fase automatica del rollback (Fase 1 en el engine) ya revierte
        el UpdateMany restaurando los documentos al estado original
        (sin el campo source_of_changes).

        Por tanto, este metodo no requiere logica adicional.
        """
        logger.info(
            "La reversion automatica de datos cubre el UpdateMany. "
            "No se requiere down() programatico para esta migracion."
        )