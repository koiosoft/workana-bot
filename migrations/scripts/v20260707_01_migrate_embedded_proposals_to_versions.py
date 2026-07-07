"""Migracion: Extrae propuestas embebidas de 'projects' y las migra a 'proposal_versions'.

Reglas de negocio:
  - Solo proyectos con campo 'proposal' no nulo y sin 'deleted_at'.
  - Se omite si ya existe al menos una version en 'proposal_versions' para ese proyecto.
  - Inserta version_number=1, refinement_log=None.
  - created_at toma el valor de proposal_at si existe; si no, now().
  - Elimina el campo 'proposal' del documento de proyecto tras la migracion.
"""

import asyncio
from datetime import datetime, timezone
from loguru import logger
from pymongo.database import Database

from app.database.mongo import connect_to_mongo, close_mongo_connection
from migrations.core.base import IMigrationContext, MigrationBase

PROJECTS_COLLECTION = "projects"
VERSIONS_COLLECTION = "proposal_versions"


class Migration(MigrationBase):
    """
    Migra el campo 'proposal' embebido en la coleccion 'projects' hacia
    la coleccion independiente 'proposal_versions'.

    Cada proyecto con propuesta embebida genera una entrada en proposal_versions
    con version_number=1, y posteriormente se elimina el campo 'proposal' del
    documento original en projects.
    """

    def up(self, writer: IMigrationContext) -> None:
        logger.info("Iniciando migracion de propuestas embebidas a proposal_versions.")
        asyncio.run(self._async_up(writer))
        logger.info("Migracion de propuestas embebidas completada.")

    async def _async_up(self, writer: IMigrationContext) -> None:
        db = await connect_to_mongo()
        try:
            projects_col = db[PROJECTS_COLLECTION]
            pv_col = db[VERSIONS_COLLECTION]

            query = {
                "proposal": {"$exists": True, "$ne": None},
                "deleted_at": {"$exists": False},
            }

            total = await projects_col.count_documents(query)
            logger.info(
                f"Encontrados {total} proyectos con propuestas embebidas para migrar."
            )

            migrated = 0
            skipped = 0

            async for project in projects_col.find(query):
                project_id = str(project["_id"])
                link_hash = project.get("link_hash", "")

                # Skip if a version already exists for this project
                existing_count = await pv_col.count_documents(
                    {"project_id": project_id}
                )
                if existing_count > 0:
                    logger.debug(
                        f"Omitiendo {project_id} – ya tiene {existing_count} versiones."
                    )
                    skipped += 1
                    continue

                proposal_data = project.get("proposal")
                proposal_at = project.get("proposal_at")

                version_created_at = (
                    proposal_at
                    if isinstance(proposal_at, datetime)
                    else datetime.now(timezone.utc)
                )

                # Queue insert into proposal_versions
                writer.add_insert(
                    VERSIONS_COLLECTION,
                    {
                        "project_id": project_id,
                        "link_hash": link_hash,
                        "version_number": 1,
                        "proposal_data": proposal_data,
                        "refinement_log": None,
                        "created_at": version_created_at,
                    },
                )

                # Queue unset of proposal field from project document
                writer.add_update_one(
                    PROJECTS_COLLECTION,
                    query_filter={"_id": project["_id"]},
                    update_mutation={"$unset": {"proposal": ""}},
                )

                migrated += 1
                logger.info(
                    f"Encolada migracion para proyecto {project_id} "
                    f"(link_hash={link_hash})"
                )

            logger.info(
                f"Resumen: {migrated} migrados, {skipped} omitidos de "
                f"{total} candidatos totales."
            )
        finally:
            await close_mongo_connection()

    def down(self, db: Database) -> None:
        """
        Reversion programatica.

        La fase automatica del rollback (Fase 1 en el engine) ya revierte:
          - Inserts en proposal_versions  → delete de los documentos insertados.
          - Updates (unset de proposal)   → restore del documento original con proposal.

        Por tanto, este metodo no requiere logica adicional.
        """
        logger.info(
            "La reversion automatica de datos cubre inserts y updates. "
            "No se requiere down() programatico para esta migracion."
        )