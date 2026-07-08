"""
Repository for the ``proposal_versions`` collection.

Every proposal generation or AI-driven refinement creates a new versioned
document.  The latest version (highest ``version_number``) for a given project
is treated as the effective proposal.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from .mongo import get_database
from loguru import logger


class ProposalVersionsRepository:
    """Data-access layer for proposal version history."""

    def __init__(self) -> None:
        self._indexes_ready = False

    @property
    def collection(self):
        return get_database()["proposal_versions"]

    async def ensure_indexes(self) -> None:
        """Create performance-critical indexes if they don't exist yet."""
        if self._indexes_ready:
            return
        # Compound index for efficient latest-version lookups
        await self.collection.create_index(
            [("project_id", ASCENDING), ("version_number", DESCENDING)],
            name="project_id_version_desc",
        )
        # Single-field index for aggregation grouping
        await self.collection.create_index(
            [("project_id", ASCENDING)], name="project_id_asc"
        )
        # Index on link_hash for querying without project_id
        await self.collection.create_index(
            [("link_hash", ASCENDING)], name="link_hash_asc"
        )
        self._indexes_ready = True

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    async def insert_version(
        self,
        project_id: str,
        link_hash: str,
        proposal_data: Dict[str, Any],
        refinement_log: Optional[List[Dict[str, Any]]] = None,
        source_of_changes: str = "IA",
        refinement_justification: Optional[str] = None,
    ) -> str:
        """Insert a new proposal version with auto-incremented version_number.

        Returns the string representation of the inserted document's _id.
        """
        await self.ensure_indexes()

        # Determine the next version number
        latest = await self.collection.find_one(
            {"project_id": project_id},
            sort=[("version_number", DESCENDING)],
            projection={"version_number": 1},
        )
        next_version = (latest["version_number"] + 1) if latest else 1

        doc: Dict[str, Any] = {
            "project_id": project_id,
            "link_hash": link_hash,
            "version_number": next_version,
            "proposal_data": proposal_data,
            "created_at": datetime.now(timezone.utc),
            "source_of_changes": source_of_changes,
        }
        if refinement_log is not None:
            doc["refinement_log"] = refinement_log
        if refinement_justification is not None:
            doc["refinement_justification"] = refinement_justification

        result = await self.collection.insert_one(doc)
        inserted_id = str(result.inserted_id)
        logger.info(
            f"Inserted proposal version {next_version} (id={inserted_id}) "
            f"for project_id={project_id}"
        )
        return inserted_id

    async def update_source_of_changes(
        self, project_id: str, source: str = "HUMAN"
    ) -> bool:
        """Update the source_of_changes field on the latest version for a project.

        Returns True if a document was updated, False otherwise.
        """
        await self.ensure_indexes()

        latest = await self.get_latest_version(project_id)
        if not latest:
            logger.warning(
                f"No proposal version found for project_id={project_id}; "
                f"cannot update source_of_changes."
            )
            return False

        version_id = latest["_id"]
        result = await self.collection.update_one(
            {"_id": ObjectId(version_id)},
            {"$set": {"source_of_changes": source}},
        )

        if result.modified_count > 0:
            logger.info(
                f"Updated source_of_changes to '{source}' for version "
                f"{version_id} of project_id={project_id}"
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Query – latest version
    # ------------------------------------------------------------------

    async def get_latest_version(
        self, project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent proposal version for *project_id*."""
        await self.ensure_indexes()
        doc = await self.collection.find_one(
            {"project_id": project_id},
            sort=[("version_number", DESCENDING)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_latest_version_by_link_hash(
        self, link_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent proposal version for *link_hash*."""
        await self.ensure_indexes()
        doc = await self.collection.find_one(
            {"link_hash": link_hash},
            sort=[("version_number", DESCENDING)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # ------------------------------------------------------------------
    # Query – version history
    # ------------------------------------------------------------------

    async def get_version_history(
        self, project_id: str
    ) -> List[Dict[str, Any]]:
        """Return all proposal versions for a project, newest first."""
        await self.ensure_indexes()
        cursor = self.collection.find({"project_id": project_id}).sort(
            [("version_number", DESCENDING)]
        )
        results: List[Dict[str, Any]] = await cursor.to_list(length=None)
        for r in results:
            r["_id"] = str(r["_id"])
        return results

    # ------------------------------------------------------------------
    # Aggregation – latest versions for multiple projects
    # ------------------------------------------------------------------

    async def get_latest_versions_for_projects(
        self, project_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Given a list of project_id strings, return a mapping of
        project_id → latest proposal data dict.

        Uses an aggregation pipeline that groups by project_id and picks the
        version with the highest version_number.
        """
        if not project_ids:
            return {}

        await self.ensure_indexes()

        pipeline: List[Dict[str, Any]] = [
            {"$match": {"project_id": {"$in": project_ids}}},
            {"$sort": {"version_number": -1}},
            {
                "$group": {
                    "_id": "$project_id",
                    "latest": {"$first": "$$ROOT"},
                }
            },
        ]

        result: Dict[str, Dict[str, Any]] = {}
        async for doc in self.collection.aggregate(pipeline):
            project_id = doc["_id"]
            latest = doc["latest"]
            latest["_id"] = str(latest["_id"])
            result[project_id] = latest

        return result

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def count_versions(self, project_id: str) -> int:
        """Return the total number of versions stored for a project."""
        await self.ensure_indexes()
        return await self.collection.count_documents({"project_id": project_id})

    async def delete_versions_for_project(self, project_id: str) -> int:
        """Remove all proposal versions for a project.  Returns count removed."""
        await self.ensure_indexes()
        result = await self.collection.delete_many({"project_id": project_id})
        return int(result.deleted_count or 0)