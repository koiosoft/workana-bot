import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict, List
from pymongo import ASCENDING, UpdateOne
from bson import ObjectId
from .mongo import get_database
from loguru import logger

class ProjectsRepository:
    def __init__(self):
        self._indexes_ready = False

    @property
    def collection(self):
        """Obtiene la colección de forma dinámica asegurando que la DB ya inició."""
        return get_database()["projects"]

    async def ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.collection.create_index([("link_hash", ASCENDING)], unique=True)
        await self.collection.create_index([("proposal_status", ASCENDING)])
        await self.collection.create_index([("scraped_at", ASCENDING)])
        await self.collection.create_index([("processing_started_at", ASCENDING)])
        await self.collection.create_index([("estimated_published_at", ASCENDING)])
        self._indexes_ready = True

    @staticmethod
    def _build_hash(project: dict[str, Any]) -> str:
        raw = project.get("link") or f"{project.get('title', '')}|{project.get('budget', '')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _calculate_estimated_published_at(self, published_str: str, scraped_at_dt: datetime) -> datetime | None:
        """
        Calcula la fecha de publicación estimada a partir de un string de tiempo relativo.
        """
        if not published_str or not isinstance(scraped_at_dt, datetime):
            return None

        # Normalize: lowercase, strip filler words, convert word-numbers to digits
        normalized = published_str.lower().strip()
        for filler in ['casi ', 'aproximadamente ', 'alrededor de ']:
            normalized = normalized.replace(filler, '')
        for word, digit in [('una ', '1 '), ('un ', '1 '), ('dos ', '2 '), ('tres ', '3 '),
                            ('cuatro ', '4 '), ('cinco ', '5 '), ('seis ', '6 '),
                            ('siete ', '7 '), ('ocho ', '8 '), ('nueve ', '9 '), ('diez ', '10 ')]:
            normalized = normalized.replace(word, digit)

        time_patterns = {
            'months': re.compile(r"hace\s+(?P<value>\d+)\s+mes(es)?", re.IGNORECASE),
            'days': re.compile(r"hace\s+(?P<value>\d+)\s+d[íi]a(s)?", re.IGNORECASE),
            'hours': re.compile(r"hace\s+(?P<value>\d+)\s+hora(s)?", re.IGNORECASE),
            'minutes': re.compile(r"hace\s+(?P<value>\d+)\s+minuto(s)?", re.IGNORECASE),
            'moment': re.compile(r"hace\s+((un|1)\s+momento|menos\s+de\s+(un|1)\s+minuto)", re.IGNORECASE)
        }

        delta = None
        if 'ayer' in normalized:
            delta = timedelta(days=1)
        else:
            for unit, pattern in time_patterns.items():
                match = pattern.search(normalized)
                if match:
                    if unit == 'moment':
                        delta = timedelta(minutes=1)
                    else:
                        value = int(match.group('value'))
                        if unit == 'months':
                            delta = timedelta(days=value * 30)
                        else:
                            delta = timedelta(**{unit: value})
                    break

        if delta:
            return scraped_at_dt - delta

        logger.warning(f"No se pudo parsear el tiempo relativo '{published_str}'.")
        return None

    async def save_scraped_projects(self, projects: list[dict[str, Any]]) -> dict[str, int]:
        await self.ensure_indexes()
        if not projects:
            return {"inserted": 0, "existing": 0}

        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        operations = []
        for project in projects:
            link_hash = self._build_hash(project)
            published_str = project.get("published", "N/A")

            doc = {
                "title": project.get("title", "N/A"),
                "budget": project.get("budget", "N/A"),
                "link": project.get("link", "N/A"),
                "published": published_str,
                "short_description": project.get("short_description", ""),
                "bids": project.get("bids", "0"),
                "source": "workana",
                "proposal_status": "pending",
                "scraped_at": now_iso,
                "link_hash": link_hash,
                "skills": project.get("skills", []),
            }

            estimated_date = self._calculate_estimated_published_at(published_str, now_dt)
            if estimated_date:
                doc["estimated_published_at"] = estimated_date

            operations.append(
                UpdateOne(
                    {"link_hash": link_hash},
                    {
                        "$setOnInsert": doc,
                        "$set": {"updated_at": now_iso},
                    },
                    upsert=True,
                )
            )

        result = await self.collection.bulk_write(operations, ordered=False)
        inserted = int(result.upserted_count or 0)
        existing = len(projects) - inserted
        return {"inserted": inserted, "existing": existing}

    async def get_pending_projects(self, limit: int = 20) -> list[dict[str, Any]]:
        await self.ensure_indexes()
        cursor = self.collection.find(
            {"proposal_status": "pending", "deleted_at": {"$exists": False}},
            {"_id": 0, "title": 1, "budget": 1, "link": 1, "published": 1, "link_hash": 1},
        ).sort("scraped_at", ASCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def claim_pending_projects(self, limit: int = 20) -> list[dict[str, Any]]:
        await self.ensure_indexes()

        cursor = self.collection.find(
            {"proposal_status": "pending", "deleted_at": {"$exists": False}},
            {"link_hash": 1},
            limit=limit
        )
        pending_items = await cursor.to_list(length=limit)
        if not pending_items:
            return []

        link_hashes = [p["link_hash"] for p in pending_items if p.get("link_hash")]
        now = datetime.now(timezone.utc).isoformat()

        result = await self.collection.update_many(
            {
                "link_hash": {"$in": link_hashes}, 
                "proposal_status": "pending"
            },
            {
                "$set": {
                    "proposal_status": "processing", 
                    "processing_started_at": now, 
                    "updated_at": now
                }
            },
        )

        if result.modified_count == 0:
            return []

        cursor = self.collection.find(
            {
                "link_hash": {"$in": link_hashes}, 
                "proposal_status": "processing",
                "processing_started_at": now
            },
            {
                "_id": 0, "title": 1, "budget": 1, "link": 1, 
                "published": 1, "short_description": 1, "link_hash": 1, "bids": 1,
                "skills": 1
            },
            sort=[("scraped_at", ASCENDING)]
        )

        return await cursor.to_list(length=limit)

    async def mark_projects_status(self, link_hashes: list[str], status: str) -> int:
        await self.ensure_indexes()
        if not link_hashes:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        result = await self.collection.update_many(
            {"link_hash": {"$in": link_hashes}},
            {"$set": {"proposal_status": status, "updated_at": now}},
        )
        return int(result.modified_count or 0)

    async def update_project_analysis(self, link_hash: str, score: int, reason: str, strategy: str = "none", status: str = "analyzed", ai_summary: str = "No summary available", contract_type: str = "project_fixed") -> bool:
        """
        Actualiza un proyecto con los resultados del análisis de la IA.
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()

        result = await self.collection.update_one(
            {"link_hash": link_hash},
            {
                "$set": {
                    "strategy": strategy,
                    "ai_score": score,
                    "ai_reason": reason,
                    "ai_summary": ai_summary,
                    "contract_type": contract_type,
                    "proposal_status": status,
                    "updated_at": now,
                    "analyzed_at": now
                }
            }
        )

        if result.modified_count > 0:
            logger.info(f"✅ Proyecto {link_hash} actualizado con score {score} y tipo {contract_type}.")
            return True

        logger.warning(f"⚠️ No se pudo actualizar el análisis para el hash: {link_hash}")
        return False

    async def reset_orphaned_proposals(self) -> int:
        """
        Resetea todos los proyectos huérfanos en estado 'ready_for_proposal' de vuelta a 'analyzed'.
        Esto limpia proyectos que quedaron atascados por interrupciones del proceso.
        Elimina TODA la data de scraping profundo para que vuelvan a ser procesados desde cero.
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()

        result = await self.collection.update_many(
            {
                "proposal_status": "ready_for_proposal",
                "deleted_at": {"$exists": False}
            },
            {
                "$set": {
                    "proposal_status": "analyzed",
                    "updated_at": now,
                    "reset_at": now
                },
                "$unset": {
                    "full_description": "",
                    "budget_detail": "",
                    "proposal": "",
                    "proposal_at": "",
                    "temp_proposal_data": "",
                    "proposal_draft": ""
                }
            }
        )

        if result.modified_count > 0:
            logger.warning(f"🔄 Reset automático: {result.modified_count} proyectos huérfanos revertidos de 'ready_for_proposal' a 'analyzed'")

        return result.modified_count

    async def get_projects_for_deep_analysis(self, min_score: int = 5, limit: int = 10) -> list[dict[str, Any]]:
        """Obtiene proyectos analizados con buen score que NO tienen descripción completa."""
        cursor = self.collection.find({
            "proposal_status": "analyzed",
            "ai_score": {"$gte": min_score},
            "full_description": {"$exists": False}
        }, {
            "_id": 0,
            "title": 1,
            "budget": 1,
            "link": 1,
            "link_hash": 1,
            "strategy": 1,
            "contract_type": 1,
            "ai_score": 1,
            "ai_summary": 1
        }).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_full_details(self, link_hash: str, details: dict):
        """Actualiza el proyecto con la data profunda y cambia el estado."""
        await self.ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()

        result = await self.collection.update_one(
            {"link_hash": link_hash},
            {
                "$set": {
                    "full_description": details.get("full_description"),
                    "skills": details.get("skills"),
                    "budget_detail": details.get("budget_detail"),
                    "proposal_status": "ready_for_proposal",
                    "updated_at": now
                }
            }
        )
        return result.modified_count > 0

    async def update_project_proposal(self, link_hash: str, proposal: dict[str, Any]):
        await self.ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()

        result = await self.collection.update_one(
            {"link_hash": link_hash},
            {
                "$set": {
                    "proposal": proposal,
                    "proposal_status": "proposal_generated",
                    "proposal_at": now,
                    "updated_at": now
                }
            }
        )

        if result.modified_count > 0:
            logger.info(f"✅ Propuesta guardada en DB para el proyecto: {link_hash}")
            return True
        return False

    async def get_project_by_hash(self, link_hash: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"link_hash": link_hash})

    # ---------- NEW METHODS ----------
    async def delete_projects(self, from_date: str | None = None) -> int:
        """
        Soft-delete projects. If from_date is provided (YYYY-MM-DD), delete
        projects with estimated_published_at >= from_date. Otherwise delete all.
        Returns the count of deleted projects.
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()

        query: dict[str, Any] = {"deleted_at": {"$exists": False}}
        if from_date:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query["estimated_published_at"] = {"$gte": from_dt}

        result = await self.collection.update_many(
            query,
            {"$set": {"deleted_at": now, "updated_at": now}}
        )
        return int(result.modified_count or 0)

    async def prune_projects(self) -> int:
        """
        Physically delete all projects that have been soft-deleted
        (i.e., have deleted_at set). Returns the count of removed projects.
        """
        await self.ensure_indexes()

        result = await self.collection.delete_many(
            {"deleted_at": {"$exists": True}}
        )
        count = int(result.deleted_count or 0)
        logger.info(f"🧹 Pruned {count} soft-deleted projects.")
        return count

    async def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a project by its MongoDB _id (as string)."""
        try:
            obj_id = ObjectId(project_id)
        except Exception:
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def update_project_by_id(self, project_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a project by its MongoDB _id. Returns True if modified."""
        try:
            obj_id = ObjectId(project_id)
        except Exception:
            return False
        now = datetime.now(timezone.utc).isoformat()
        update_data["updated_at"] = now
        result = await self.collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    # ---------- END NEW METHODS ----------

    async def get_projects(
        self,
        status: str = "all",
        search_term: Optional[str] = None,
        staff_augmentation_only: bool = False,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        # 1. Base Exclusions
        query: Dict[str, Any] = {
            "proposal_status": {"$ne": "not_found"},
            "deleted_at": {"$exists": False}
        }

        # 2. Status and AI Score Filtering
        if status == "discarded":
            query["ai_score"] = {"$lt": 5}
        elif status == "rejected":
            query["proposal_status"] = "rejected"
        else:
            query["ai_score"] = {"$gte": 5}
            if status == "all":
                query["proposal_status"] = {
                    "$in": ["proposal_generated", "submited_to_workana", "ready_for_proposal"]
                }
            else:
                query["proposal_status"] = status

        # 3. Search Term Filtering
        if search_term:
            query["$or"] = [
                {"title": {"$regex": search_term, "$options": "i"}},
                {"short_description": {"$regex": search_term, "$options": "i"}},
                {"full_description": {"$regex": search_term, "$options": "i"}}
            ]

        # 4. Contract Type Filtering
        if staff_augmentation_only:
            query["contract_type"] = "staff_augmentation"

        skip = (page - 1) * limit

        total = await self.collection.count_documents(query)
        
        cursor = self.collection.find(query).sort([
            ("estimated_published_at", -1),
            ("ai_score", -1),
            ("updated_at", -1)
        ]).skip(skip).limit(limit)

        projects = await cursor.to_list(length=limit)

        # Convert ObjectId to string for JSON serialization
        for p in projects:
            p["_id"] = str(p["_id"])

        return {
            "projects": projects,
            "total": total
        }
