import asyncio
from datetime import datetime, timezone
from loguru import logger
from pymongo.database import Database

# Since migrations/main.py adds the root to sys.path, these imports are valid
from app.database.mongo import close_mongo_connection, connect_to_mongo
from app.database.projects_repository import ProjectsRepository
from app.scraper.factory import ScraperFactory
from app.intelligence.factory import get_intelligence_service

from migrations.core.base import IMigrationContext, MigrationBase


TARGET_COLLECTION = "projects"


class Migration(MigrationBase):
    """
    Backfills the 'full_description' field for projects that have a generated
    proposal but are missing this information. It scrapes the project details,
    formats the description using the AI service, and updates the database.
    """

    def up(self, writer: IMigrationContext) -> None:
        """
        Applies the changes to backfill the full_description.
        """
        logger.info("Starting backfill for 'full_description' field.")
        # The migration runner is sync, so we create a new event loop to run async code.
        asyncio.run(self._async_up(writer))
        logger.info("Backfill for 'full_description' completed.")

    async def _async_up(self, writer: IMigrationContext):
        """
        Orchestrates the asynchronous operations for the backfill.
        """
        await connect_to_mongo(None)
        try:
            repo = ProjectsRepository()
            await repo.ensure_indexes()
            scraper = ScraperFactory.get_scraper()
            ai_service = get_intelligence_service()

            projects_to_update = await repo.collection.find(
                {"proposal_status": "proposal_generated", "full_description": {"$exists": False}}
            ).to_list(length=None)

            if not projects_to_update:
                logger.info("No projects found that need a description backfill.")
                return

            logger.info(f"Found {len(projects_to_update)} projects to backfill with full descriptions.")

            for project in projects_to_update:
                link_hash = project.get("link_hash")
                url = project.get("link")
                title = project.get("title", "N/A")

                if not url or not link_hash:
                    logger.warning(f"Skipping project with missing link or hash: {title}")
                    continue

                logger.info(f"Processing project: {title} ({link_hash})")
                try:
                    full_detail = await scraper.fetch_full_detail(url)

                    if not full_detail:
                        logger.warning(f"Could not fetch details for project: {title}. Marking as 'backfill_failed'.")
                        writer.add_update_one(
                            collection_name=TARGET_COLLECTION,
                            query_filter={"link_hash": link_hash},
                            update_mutation={"$set": {"proposal_status": "backfill_failed"}},
                        )
                        continue

                    formatted_description = full_detail.get("full_description", "")
                    raw_description = full_detail.get("full_description")
                    if raw_description:
                        # The circuit breaker is not available in migrations, so we call it directly.
                        formatted_description = await ai_service.format_project_description(raw_description)

                    update_payload = {
                        "full_description": formatted_description,
                        "skills": full_detail.get("skills"),
                        "budget_detail": full_detail.get("budget_detail"),
                        "migration_backfilled_at": datetime.now(timezone.utc),
                    }

                    writer.add_update_one(
                        collection_name=TARGET_COLLECTION,
                        query_filter={"link_hash": link_hash},
                        update_mutation={"$set": update_payload},
                    )
                    logger.success(f"Successfully queued update for project: {url}")

                except Exception as e:
                    logger.error(f"Failed to process project {title}. Error: {e}", exc_info=True)
                    writer.add_update_one(
                        collection_name=TARGET_COLLECTION,
                        query_filter={"link_hash": link_hash},
                        update_mutation={"$set": {"proposal_status": "backfill_failed"}},
                    )
        finally:
            await close_mongo_connection(None)

    def down(self, db: Database) -> None:
        """
        Reverts the changes made by the 'up' method by removing the backfilled data.
        """
        logger.info("Reverting backfilled full_descriptions.")
        result = db[TARGET_COLLECTION].update_many(
            {"migration_backfilled_at": {"$exists": True}},
            {
                "$unset": {
                    "full_description": "",
                    "skills": "",
                    "budget_detail": "",
                    "migration_backfilled_at": "",
                }
            },
        )
        logger.info(f"Reverted {result.modified_count} projects.")
