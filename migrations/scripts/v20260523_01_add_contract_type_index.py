"""
Migration: Add contract_type index to projects collection
Date: 2026-05-23
Description: Adds an index on the contract_type field to improve query performance
             for filtering projects by contract type (project_fixed vs staff_augmentation)
"""

from logging import getLogger
from typing import cast

from pymongo import ASCENDING
from pymongo.database import Database
from pymongo.errors import OperationFailure

from migrations.core.base import IMigrationContext, MigrationBase
from migrations.core.writer import ResilientBulkWriter

logger = getLogger(__name__)


class Migration(MigrationBase):
    """
    Agrega un índice en contract_type y un valor por defecto si no existe.
    """

    def up(self, writer: IMigrationContext) -> None:
        """
        Applies the migration.
        """
        concrete_writer = cast(ResilientBulkWriter, writer)
        db = concrete_writer.db

        writer.add_update(
            collection_name="projects",
            filter_query={"contract_type": {"$exists": False}},
            update_query={"$set": {"contract_type": "project_fixed"}}
        )

        logger.info("Creando índice en 'contract_type'...")
        try:
            db.projects.create_index(
                [("contract_type", ASCENDING)],
                name="idx_contract_type"
            )
            logger.info("Índice 'idx_contract_type' creado exitosamente.")
        except OperationFailure as e:
            if "already exists" in str(e):
                logger.warning("El índice 'idx_contract_type' ya existía.")
            else:
                raise

    def down(self, db: Database) -> None:
        """
        Reverts the migration.
        """
        try:
            db.projects.drop_index("idx_contract_type")
            logger.info("Índice 'idx_contract_type' eliminado exitosamente.")
        except OperationFailure:
            logger.warning("No se pudo eliminar el índice 'idx_contract_type' (probablemente no existía).")
